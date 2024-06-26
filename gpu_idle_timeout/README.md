# GPU Idle Timeout
Monitors GPU usage, if usage drops below a threshhold for specified time window, the task will be killed.

# Help
```
$ python gpu_idle_timeout.py --help
usage: gpu_idle_timeout [-h] [-t THRESHHOLD_PERCENTAGE] [-s SAMPLE_FREQ] [-n NUM_SAMPLES] [-d DELAY_SAMPLES] [-a ALL_OR_ANY] [-x] ...

Terminates when GPU usage drops below threshhold during sample window. Note: requires 'nvidia-smi' binary to be accessible in PATH

optional arguments:
  -h, --help            show this help message and exit
  -t THRESHHOLD_PERCENTAGE, --threshhold-percentage THRESHHOLD_PERCENTAGE
                        Threshhold in percentage of GPU usage which triggers a task termination. Must be greater than 0. (default: 1)
  -s SAMPLE_FREQ, --sample-freq SAMPLE_FREQ
                        How frequently, in seconds, to sample the GPU usage. Must be greater than 0. (default: 5)
  -n NUM_SAMPLES, --num-samples NUM_SAMPLES
                        Number of samples in window used to evaluate GPU usage. Must be greater than 0. (default: 60)
  -d DELAY_SAMPLES, --delay-samples DELAY_SAMPLES
                        Number of samples to delay before evaluating GPU usage. (default: 12)
  -a ALL_OR_ANY, --all_or_any ALL_OR_ANY
                        Whether to verify that all or any of the GPUs have the specified threshold. Must be either all or any (default: all)
  -x, --debug           Enable debug logging (reports GPU readings each sample period). (default: False)
```

# Description

1. We launch the `watcher` process to start monitoring GPU usage.
2. We wait SAMPLE_FREQ * DELAY_SAMPLES seconds before starting to monitor. This is to account for instances in which the `exec_command_and_args` takes some time to start using the GPU.
3. Every SAMPLE_FREQ seconds we record the GPU usage for all GPUs on the system.
4. We do not do any evaluation of the usage metrics until NUM_SAMPLES samples have been collected
5. Once the above condition is true, we check if the GPU usage was below THRESHHOLD_PERCENTAGE on *any* or *all* GPUs. If so, the task is terminated.


# Cluster-wide GPU utilization timeout

This script can be automatically launched by any determined task (notebook/shell) to monitor the GPU utilization and kill any tasks that are not fully utilizing the specified `THRESHOLD_PERCENTAGE` argument for the total number of samples.

Make sure to save this script in a path that's accessible by the master and agent instances. Here's a blurb from a sample `master.yaml` with this script added

```yaml
task_container_defaults:
  startup_hook: python /path/to/sharedfs/gpu_idle_timeout.py -t 50 -s 30 -n 6 -d 2 -a any -x &
```
