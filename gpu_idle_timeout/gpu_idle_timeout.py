import determined
import argparse
import collections
import logging
import os
import psutil
import re
import sys
import signal
import time
import subprocess
import shutil


class IdleGpuWatcher:
    def __init__(
        self,
        threshhold_percentage: int,
        sample_freq: int,
        num_samples: int,
        delay_samples: int,
        signal_code: int,
        signal_children: bool,
    ):
        if not shutil.which("nvidia-smi"):
            raise RuntimeError("Unable to locate 'nvidia-smi'")

        self._num_samples = num_samples
        self._sample_freq = sample_freq
        self._full_window = sample_freq * num_samples
        self._threshhold_percentage = threshhold_percentage
        self._delay_samples = delay_samples
        self._signal_code = signal_code
        self._signal_children = signal_children

        header_regstr = {
            "uuid": r"(?P<uuid>[a-zA-Z0-9-]+)",
            "utilization.gpu": r"(?P<gpu_util>[0-9]+) %",
        }
        line_regstr = ", ".join(header_regstr.values())
        query_gpu = ",".join(header_regstr.keys())

        self._nvida_smi_cmd = [
            "nvidia-smi",
            "--format=csv,noheader",
            f"--query-gpu={query_gpu}",
        ]
        self._line_regex = re.compile(line_regstr)
        self._gpu_util_samples: dict[
            str, collections.deque
        ] = {}  # gpu_uuid: <circular queue of samples>

    def _get_nvidia_smi(self) -> dict[str, int]:
        # nvidia-smi --help-query-gpu: "utilization.gpu":
        # Percent of time over the past sample period during which one or more kernels was
        # executing on the GPU. The sample period may be between 1 second and 1/6 second
        # depending on the product.
        output = {}

        csv_output = subprocess.check_output(self._nvida_smi_cmd).decode()
        for line in csv_output.splitlines():
            match = re.match(self._line_regex, line)
            if match is None:
                raise RuntimeError(f"Unexpected output format: {line}")

            data = match.groupdict()
            output[data["uuid"]] = int(data["gpu_util"])
        return output

    def _check_idle(self) -> bool:
        gpu_utils = self._get_nvidia_smi()

        idle_gpus: dict[str, bool] = {k: False for k in gpu_utils.keys()}

        for gpu_uuid, gpu_util in gpu_utils.items():
            logging.debug(f"{gpu_uuid} usage {gpu_util}%")
            if self._gpu_util_samples.get(gpu_uuid) is None:
                self._gpu_util_samples[gpu_uuid] = collections.deque()

            self._gpu_util_samples[gpu_uuid].append(gpu_util)

            if len(self._gpu_util_samples[gpu_uuid]) < self._num_samples:
                continue

            if all(
                s < self._threshhold_percentage
                for s in self._gpu_util_samples[gpu_uuid]
            ):
                idle_gpus[gpu_uuid] = True

            self._gpu_util_samples[gpu_uuid].popleft()

        if all(idle for idle in idle_gpus.values()):
            logging.error(
                f"usage for all GPUs: {[uuid for uuid in idle_gpus.keys()]} was "
                f"below threshhold {self._threshhold_percentage}% "
                f"for last {self._sample_freq * self._num_samples} seconds."
            )
            return True
        return False

    def _flatten_process_tree(
        self,
        p: psutil.Process,
        depth: int = 0,
        proc_layers: list[list[psutil.Process]] = [],
    ) -> list[list[psutil.Process]]:
        # DFS and build process layers
        if len(proc_layers) == depth:
            proc_layers.append([])

        proc_layers[depth].append(p)

        children = p.children()
        if children:
            for cp in children:
                self._flatten_process_tree(cp, depth + 1, proc_layers)

        if depth == 0:
            return proc_layers

    def watch_process(self, exec_command_and_args: list[str]) -> int:
        info = determined.get_cluster_info()
        p = subprocess.Popen(exec_command_and_args)
        logging.info(
            f"Starting GPU idle watcher: threshhold_percentage={self._threshhold_percentage}%, "
            f"sample_freq={self._sample_freq}, num_samples={self._num_samples}, "
            f"delay_samples={self._delay_samples}, window_size={self._full_window}"
        )
        try:
            while True:
                if p.poll() is None:
                    time.sleep(self._sample_freq)

                    if self._delay_samples > 1:
                        self._delay_samples -= 1
                        logging.info(
                            "waiting for delay samples. "
                            f"{self._delay_samples * self._sample_freq} seconds left"
                        )
                        continue

                    if self._check_idle():
                        if self._signal_children:
                            proc_layers = self._flatten_process_tree(psutil.Process(p.pid))

                            logging.info("signal children: logging process tree")
                            for num, layer in enumerate(proc_layers):
                                for proc in layer:
                                    cmdline = " ".join(proc.cmdline())
                                    logging.info(f"signal children: layer {num}: pid {proc.pid}: '{cmdline}'")

                            # ~ reverse layer order BFS signal the children
                            logging.info("signal children: signalling started")
                            for ii in range(len(proc_layers) - 1, 0, -1):
                                for proc in proc_layers[ii]:
                                    logging.info(
                                        f"signal children: send signal {self._signal_code}"
                                        f"to pid {proc.pid} in layer {ii}"
                                    )
                                    psutil.Process(proc.pid).send_signal(self._signal_code)

                            logging.info("signal children: signaling ended")

                        logging.info(f"Sending signal {self._signal_code} to process {p.pid}")
                        p.send_signal(self._signal_code)
                        time.sleep(3)  # Wait for signal handlers
                        task_type = info.task_type.lower()
                        task_id = info.task_id
                        subprocess.Popen(f'det {task_type} kill {task_id}', shell=True)
                        sys.exit(1)

                    continue

                break

        finally:
            if p.poll() is None:
                logging.error("process still alive, maybe hung, killing.")
                p.kill()  # SIGKILL because it is likely hung

        return p.wait()


def configure_logging(debug: bool = False) -> None:
    level = logging.INFO
    if debug:
        level = logging.DEBUG
    logging_format = "%(asctime)s: %(levelname)s: %(module)s: %(message)s"
    logging.basicConfig(format=logging_format, level=level)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="gpu_idle_timeout",
        description=(
            "Launches a process and terminates when GPU usage drops below "
            "threshhold during sample window.\n"
            "Note: requires 'nvidia-smi' binary to be accessible in PATH"
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="",
    )
    parser.add_argument(
        "-t",
        "--threshhold-percentage",
        type=int,
        default=1,
        help=(
            "Threshhold in percentage of GPU usage which triggers a failure. "
            "Must be greater than 0."
        ),
    )
    parser.add_argument(
        "-s",
        "--sample-freq",
        type=int,
        default=5,
        help="How frequently, in seconds, to sample the GPU usage. Must be greater than 0.",
    )
    parser.add_argument(
        "-n",
        "--num-samples",
        type=int,
        default=60,
        help="Number of samples in window used to evaluate GPU usage. Must be greater than 0.",
    )
    parser.add_argument(
        "-d",
        "--delay-samples",
        type=int,
        default=12,
        help="Number of samples to delay before evaluating GPU usage.",
    )
    parser.add_argument(
        "--signal-name",
        type=str,
        default="SIGQUIT",
        help="signal to send to the process before killing it.",
    )
    parser.add_argument(
        "--signal-children",
        default=False,
        action="store_true",
        help="Whether to signal the children of the process first."
    )
    parser.add_argument(
        "-x",
        "--debug",
        default=False,
        action="store_true",
        help="Enable debug logging (reports GPU readings each sample period).",
    )

    parser.add_argument(
        "exec_command_and_args",
        nargs=argparse.REMAINDER,
        help="Command and arguments to execute",
    )
    args = parser.parse_args()

    if not args.exec_command_and_args:
        parser.print_help()
        sys.stderr.write(
            "\nERROR: You must append the program and arguments you would like to execute.\n"
        )
        sys.exit(1)

    # FIXME:
    # XXX There should be a way to force ints to be positive and non-zero
    if args.threshhold_percentage < 1:
        parser.print_help()
        sys.stderr.write("\nERROR: THRESHHOLD_PERCENTAGE must be greater than 0.\n")
        sys.exit(1)

    if args.sample_freq < 1:
        parser.print_help()
        sys.stderr.write("\nERROR: SAMPLE_FREQ must be greater than 0.\n")
        sys.exit(1)

    if args.num_samples < 1:
        parser.print_help()
        sys.stderr.write("\nERROR: NUM_SAMPLES must be greater than 0.\n")
        sys.exit(1)

    if args.num_samples < 1:
        parser.print_help()
        sys.stderr.write("\nERROR: NUM_SAMPLES must be greater than 0.\n")
        sys.exit(1)

    try:
        signal_code = int(getattr(signal, args.signal_name))
    except AttributeError as e:
        parser.print_help()
        sys.stderr.write(f"\nERROR: unknown SIGNAL '{args.signal_name}'.\n")
        sys.exit(1)

    if args.num_samples < 1:
        parser.print_help()
        sys.stderr.write("\nERROR: NUM_SAMPLES must be greater than 0.\n")
        sys.exit(1)

    if not shutil.which("nvidia-smi"):
        parser.print_help()
        sys.stderr.write("\nERROR: Unable to locate 'nvidia-smi'\n")
        sys.exit(1)

    configure_logging(args.debug)

    watcher = IdleGpuWatcher(
        threshhold_percentage=args.threshhold_percentage,
        sample_freq=args.sample_freq,
        num_samples=args.num_samples,
        delay_samples=args.delay_samples,
        signal_code=signal_code,
        signal_children=args.signal_children,
    )

    sys.exit(watcher.watch_process(args.exec_command_and_args))