# GPU Idle Timeout
Launch a process and watch GPU usage. If usage drops below a threshhold for specified time window, the process will be killed.

# Help
```
$ python gpu_idle_timeout.py --help
usage: gpu_idle_timeout [-h] [-t THRESHHOLD_PERCENTAGE] [-s SAMPLE_FREQ] [-n NUM_SAMPLES] [-d DELAY_SAMPLES] [--signal-name SIGNAL_NAME] [--signal-children] [-x] ...

Launches a process and terminates when GPU usage drops below threshhold during sample window. Note: requires 'nvidia-smi' binary to be accessible in PATH

positional arguments:
  exec_command_and_args
                        Command and arguments to execute

optional arguments:
  -h, --help            show this help message and exit
  -t THRESHHOLD_PERCENTAGE, --threshhold-percentage THRESHHOLD_PERCENTAGE
                        Threshhold in percentage of GPU usage which triggers a failure. Must be greater than 0. (default: 1)
  -s SAMPLE_FREQ, --sample-freq SAMPLE_FREQ
                        How frequently, in seconds, to sample the GPU usage. Must be greater than 0. (default: 5)
  -n NUM_SAMPLES, --num-samples NUM_SAMPLES
                        Number of samples in window used to evaluate GPU usage. Must be greater than 0. (default: 60)
  -d DELAY_SAMPLES, --delay-samples DELAY_SAMPLES
                        Number of samples to delay before evaluating GPU usage. (default: 12)
  --signal-name SIGNAL_NAME
                        signal to send to the process before killing it. (default: SIGQUIT)
  --signal-children     Whether to signal the children of the process first. (default: False)
  -x, --debug           Enable debug logging (reports GPU readings each sample period). (default: False)
```

# Description

1. We launch the `exec_command_and_args` in a subprocess.
2. We wait SAMPLE_FREQ * DELAY_SAMPLES seconds before starting to monitor. This is to account for instances in which the `exec_command_and_args` takes some time to start using the GPU.
3. Every SAMPLE_FREQ seconds we record the GPU usage for all GPUs on the system.
4. We do not do any evaluation of the usage metrics until NUM_SAMPLES samples have been collected
5. Once the above condition is true, we check if the GPU usage was below THRESHHOLD_PERCENTAGE on *all* samples. If so, we exit.


# Cluster-wide GPU utilization timeout

This script can be automatically launched by any determined task (notebook/shell) to monitor the GPU utilization and kill any tasks that are not fully utilizing the specified `THRESHOLD_PERCENTATE` argument for the total number of samples.

Make sure to save this script in a path that's accessible by the master and agent instances. Here's a blurb from a sample `master.yaml` with this script added:

```yaml
task_container_defaults:
  startup_hook: python /path/to/sharedfs/gpu_idle_timeout.py -t 50 -s 30 -n 6 -d 2 -x sleep 1h &
```


# Example usage:

In this example I have specified the following I am executing `grep foo`, which will just hang indefinitely, to show how this operates.

```
$ python gpu_idle_timeout.py -t 50 -s 6 -n 5 -d 3 -x grep foo
2024-03-15 11:04:29,052: INFO: gpu_idle_timeout: Starting GPU idle watcher: threshhold_percentage=50%, sample_freq=6, num_samples=5, delay_samples=3, window_size=30
2024-03-15 11:04:35,055: INFO: gpu_idle_timeout: waiting for delay samples. 12 seconds left
2024-03-15 11:04:41,061: INFO: gpu_idle_timeout: waiting for delay samples. 6 seconds left
2024-03-15 11:04:47,084: DEBUG: gpu_idle_timeout: GPU-a5b02c30-9c95-cb81-e41e-ca204d57aa3b usage 0%
2024-03-15 11:04:47,084: DEBUG: gpu_idle_timeout: GPU-b805d632-775b-c673-fe68-26b26996cd09 usage 0%
2024-03-15 11:04:53,111: DEBUG: gpu_idle_timeout: GPU-a5b02c30-9c95-cb81-e41e-ca204d57aa3b usage 0%
2024-03-15 11:04:53,111: DEBUG: gpu_idle_timeout: GPU-b805d632-775b-c673-fe68-26b26996cd09 usage 0%
2024-03-15 11:04:59,135: DEBUG: gpu_idle_timeout: GPU-a5b02c30-9c95-cb81-e41e-ca204d57aa3b usage 0%
2024-03-15 11:04:59,136: DEBUG: gpu_idle_timeout: GPU-b805d632-775b-c673-fe68-26b26996cd09 usage 0%
2024-03-15 11:05:05,157: DEBUG: gpu_idle_timeout: GPU-a5b02c30-9c95-cb81-e41e-ca204d57aa3b usage 0%
2024-03-15 11:05:05,157: DEBUG: gpu_idle_timeout: GPU-b805d632-775b-c673-fe68-26b26996cd09 usage 0%
2024-03-15 11:05:11,182: DEBUG: gpu_idle_timeout: GPU-a5b02c30-9c95-cb81-e41e-ca204d57aa3b usage 0%
2024-03-15 11:05:11,183: DEBUG: gpu_idle_timeout: GPU-b805d632-775b-c673-fe68-26b26996cd09 usage 0%
2024-03-15 11:05:11,183: ERROR: gpu_idle_timeout: usage for all GPUs: ['GPU-a5b02c30-9c95-cb81-e41e-ca204d57aa3b', 'GPU-b805d632-775b-c673-fe68-26b26996cd09'] was below threshhold 50% for last 30 seconds. Killing process.
2024-03-15 11:05:11,183: ERROR: gpu_idle_timeout: process still alive, maybe hung, killing.
```

# Determined AI Example:
```
# Grab an MNist Pytorch Example:

$ wget https://docs.determined.ai/latest/_downloads/61c6df286ba829cb9730a0407275ce50/mnist_pytorch.tgz
--2024-03-15 11:45:41--  https://docs.determined.ai/latest/_downloads/61c6df286ba829cb9730a0407275ce50/mnist_pytorch.tgz
Loaded CA certificate '/etc/ssl/certs/ca-certificates.crt'
Resolving docs.determined.ai (docs.determined.ai)... 18.160.225.126, 18.160.225.114, 18.160.225.112, ...
Connecting to docs.determined.ai (docs.determined.ai)|18.160.225.126|:443... connected.
HTTP request sent, awaiting response... 200 OK
Length: 4429 (4.3K) [application/x-tar]
Saving to: ‘mnist_pytorch.tgz’

mnist_pytorch.tgz                                           100%[==========================================================================================================================================>]   4.33K  --.-KB/s    in 0s      

2024-03-15 11:45:42 (62.1 MB/s) - ‘mnist_pytorch.tgz’ saved [4429/4429]

# Extract the archive and change into the directory:

$ tar zxvf mnist_pytorch.tgz 
mnist_pytorch/
mnist_pytorch/dist_random.yaml
mnist_pytorch/adaptive.yaml
mnist_pytorch/const.yaml
mnist_pytorch/project-caps-config.yaml
mnist_pytorch/bad-config.yaml
mnist_pytorch/model.py
mnist_pytorch/README.md
mnist_pytorch/train.py
mnist_pytorch/distributed.yaml
mnist_pytorch/data.py

$ cd mnist_pytorch/


# Copy your gpu_idle_timeout.py into your context directory.

$ cp /home/ttucker/tmp/src/varlogtim/tools/gpu_idle_timeout/gpu_idle_timeout.py .
'/home/ttucker/tmp/src/varlogtim/tools/gpu_idle_timeout/gpu_idle_timeout.py' -> './gpu_idle_timeout.py'
$ ls -ltr
total 52
-rw------- 1 ttucker ttucker  467 Aug 25  2023 project-caps-config.yaml
-rw------- 1 ttucker ttucker  531 Aug 25  2023 bad-config.yaml
-rw------- 1 ttucker ttucker 4518 Feb 28 12:59 train.py
-rw------- 1 ttucker ttucker 3279 Feb 28 12:59 README.md
-rw------- 1 ttucker ttucker  885 Feb 28 12:59 model.py
-rw------- 1 ttucker ttucker  352 Feb 28 12:59 distributed.yaml
-rw------- 1 ttucker ttucker  578 Feb 28 12:59 dist_random.yaml
-rw------- 1 ttucker ttucker  870 Feb 28 12:59 data.py
-rw------- 1 ttucker ttucker  267 Feb 28 12:59 const.yaml
-rw------- 1 ttucker ttucker  557 Feb 28 12:59 adaptive.yaml
-rw-r--r-- 1 ttucker ttucker 7610 Mar 15 11:48 gpu_idle_timeout.py


# Make a backup of the distributed.yaml config and the train.py so that we can show the changes:

$ cp distributed.yaml distributed.yaml.orig
'distributed.yaml' -> 'distributed.yaml.orig'

$ cp train.py train.py.orig
'train.py' -> 'train.py.orig'


# Now let's modify the train.py to have it sleep on the 700th batch to simulate a hang

$ diff -C2 train.py train.py.orig 
*** train.py	2024-03-15 12:13:02.048837672 -0400
--- train.py.orig	2024-03-15 11:53:36.425456429 -0400
***************
*** 20,24 ****
  import model
  import torch
- import time
  from ruamel import yaml
  from torch import nn
--- 20,23 ----
***************
*** 63,70 ****
          self, batch: pytorch.TorchData, epoch_idx: int, batch_idx: int
      ) -> Dict[str, torch.Tensor]:
-         if batch_idx > 700:
-             print(f"batch limit hit, simulating hang")
-             time.sleep(300)
- 
          batch_data, labels = batch
  
--- 62,65 ----


# Now let's modify the distributed.yaml config and set the following:

- I have two GPUs on this system, so I will set "slots_per_trial: 2"
- Set max_restarts to 0
- Modify our entrypoint in order to use our gpu_idle_timeout wrapper with the following config:
  - THRESHHOLD_PERCENTAGE: 20 percent
  - SAMPLE_FREQ: 3 seconds
  - NUM_SAMPLES: 7 samples (21 seconds of idleness)
  - DELAY_SAMPLES: 1 sample (delay 3 seconds before starting to monitor, for data download)

$ diff -C2 distributed.yaml distributed.yaml.orig 
*** distributed.yaml	2024-03-15 12:28:52.322210061 -0400
--- distributed.yaml.orig	2024-03-15 11:49:55.375447342 -0400
***************
*** 13,17 ****
    smaller_is_better: true
  resources:
!   slots_per_trial: 2
! entrypoint: python3 ./gpu_idle_timeout.py -t 20 -s 3 -n 7 -d 1 -x python3 -m determined.launch.torch_distributed python3 train.py
! max_restarts: 0
--- 13,16 ----
    smaller_is_better: true
  resources:
!   slots_per_trial: 8
! entrypoint: python3 -m determined.launch.torch_distributed python3 train.py


# Now let's launch the experiment:

$ det e create distributed.yaml ./
Preparing files to send to master... 24.3KB and 13 files
Created experiment 7


# Now let's look for key items in our log to show behavior:

$ det e logs 9 | grep -e 'simulating hang' -e 'report_training' -e 'gpu_idle_timeout:' -e 'ERROR'
[2024-03-15T16:28:57.986411Z] 5c902731 || 2024-03-15 16:28:57,986: INFO: gpu_idle_timeout: Starting GPU idle watcher: threshhold_percentage=20%, sample_freq=3, num_samples=7, delay_samples=1, window_size=21
[2024-03-15T16:29:01.008703Z] 5c902731 || 2024-03-15 16:29:01,008: DEBUG: gpu_idle_timeout: GPU-a5b02c30-9c95-cb81-e41e-ca204d57aa3b usage 37%
[2024-03-15T16:29:01.008756Z] 5c902731 || 2024-03-15 16:29:01,008: DEBUG: gpu_idle_timeout: GPU-b805d632-775b-c673-fe68-26b26996cd09 usage 19%
[2024-03-15T16:29:04.032625Z] 5c902731 || 2024-03-15 16:29:04,032: DEBUG: gpu_idle_timeout: GPU-a5b02c30-9c95-cb81-e41e-ca204d57aa3b usage 68%
[2024-03-15T16:29:04.032670Z] 5c902731 || 2024-03-15 16:29:04,032: DEBUG: gpu_idle_timeout: GPU-b805d632-775b-c673-fe68-26b26996cd09 usage 70%
[2024-03-15T16:29:06.552162Z] 5c902731 [rank=0] || INFO: [62] determined.core: report_training_metrics(steps_completed=100, metrics={'loss': 0.6182383894920349})
[2024-03-15T16:29:07.060970Z] 5c902731 || 2024-03-15 16:29:07,060: DEBUG: gpu_idle_timeout: GPU-a5b02c30-9c95-cb81-e41e-ca204d57aa3b usage 38%
[2024-03-15T16:29:07.061013Z] 5c902731 || 2024-03-15 16:29:07,060: DEBUG: gpu_idle_timeout: GPU-b805d632-775b-c673-fe68-26b26996cd09 usage 100%
[2024-03-15T16:29:08.125250Z] 5c902731 [rank=0] || INFO: [62] determined.core: report_training_metrics(steps_completed=200, metrics={'loss': 0.2463933825492859})
[2024-03-15T16:29:09.341726Z] 5c902731 [rank=0] || INFO: [62] determined.core: report_training_metrics(steps_completed=300, metrics={'loss': 0.18230664730072021})
[2024-03-15T16:29:10.081248Z] 5c902731 || 2024-03-15 16:29:10,081: DEBUG: gpu_idle_timeout: GPU-a5b02c30-9c95-cb81-e41e-ca204d57aa3b usage 70%
[2024-03-15T16:29:10.081304Z] 5c902731 || 2024-03-15 16:29:10,081: DEBUG: gpu_idle_timeout: GPU-b805d632-775b-c673-fe68-26b26996cd09 usage 63%
[2024-03-15T16:29:10.536653Z] 5c902731 [rank=0] || INFO: [62] determined.core: report_training_metrics(steps_completed=400, metrics={'loss': 0.13787135481834412})
[2024-03-15T16:29:11.704796Z] 5c902731 [rank=0] || INFO: [62] determined.core: report_training_metrics(steps_completed=500, metrics={'loss': 0.14235930144786835})
[2024-03-15T16:29:12.867088Z] 5c902731 [rank=0] || INFO: [62] determined.core: report_training_metrics(steps_completed=600, metrics={'loss': 0.11368992924690247})
[2024-03-15T16:29:13.102325Z] 5c902731 || 2024-03-15 16:29:13,102: DEBUG: gpu_idle_timeout: GPU-a5b02c30-9c95-cb81-e41e-ca204d57aa3b usage 55%
[2024-03-15T16:29:13.102369Z] 5c902731 || 2024-03-15 16:29:13,102: DEBUG: gpu_idle_timeout: GPU-b805d632-775b-c673-fe68-26b26996cd09 usage 55%
[2024-03-15T16:29:14.063351Z] 5c902731 [rank=0] || INFO: [62] determined.core: report_training_metrics(steps_completed=700, metrics={'loss': 0.12303102761507034})
[2024-03-15T16:29:14.110799Z] 5c902731 [rank=1] || batch limit hit, simulating hang
[2024-03-15T16:29:14.112529Z] 5c902731 [rank=0] || batch limit hit, simulating hang
[2024-03-15T16:29:16.124800Z] 5c902731 || 2024-03-15 16:29:16,124: DEBUG: gpu_idle_timeout: GPU-a5b02c30-9c95-cb81-e41e-ca204d57aa3b usage 0%
[2024-03-15T16:29:16.124847Z] 5c902731 || 2024-03-15 16:29:16,124: DEBUG: gpu_idle_timeout: GPU-b805d632-775b-c673-fe68-26b26996cd09 usage 1%
[2024-03-15T16:29:19.143523Z] 5c902731 || 2024-03-15 16:29:19,143: DEBUG: gpu_idle_timeout: GPU-a5b02c30-9c95-cb81-e41e-ca204d57aa3b usage 0%
[2024-03-15T16:29:19.143567Z] 5c902731 || 2024-03-15 16:29:19,143: DEBUG: gpu_idle_timeout: GPU-b805d632-775b-c673-fe68-26b26996cd09 usage 1%
[2024-03-15T16:29:22.164971Z] 5c902731 || 2024-03-15 16:29:22,164: DEBUG: gpu_idle_timeout: GPU-a5b02c30-9c95-cb81-e41e-ca204d57aa3b usage 0%
[2024-03-15T16:29:22.165030Z] 5c902731 || 2024-03-15 16:29:22,164: DEBUG: gpu_idle_timeout: GPU-b805d632-775b-c673-fe68-26b26996cd09 usage 1%
[2024-03-15T16:29:25.185820Z] 5c902731 || 2024-03-15 16:29:25,185: DEBUG: gpu_idle_timeout: GPU-a5b02c30-9c95-cb81-e41e-ca204d57aa3b usage 0%
[2024-03-15T16:29:25.185927Z] 5c902731 || 2024-03-15 16:29:25,185: DEBUG: gpu_idle_timeout: GPU-b805d632-775b-c673-fe68-26b26996cd09 usage 1%
[2024-03-15T16:29:28.208188Z] 5c902731 || 2024-03-15 16:29:28,207: DEBUG: gpu_idle_timeout: GPU-a5b02c30-9c95-cb81-e41e-ca204d57aa3b usage 0%
[2024-03-15T16:29:28.208231Z] 5c902731 || 2024-03-15 16:29:28,208: DEBUG: gpu_idle_timeout: GPU-b805d632-775b-c673-fe68-26b26996cd09 usage 1%
[2024-03-15T16:29:31.227349Z] 5c902731 || 2024-03-15 16:29:31,227: DEBUG: gpu_idle_timeout: GPU-a5b02c30-9c95-cb81-e41e-ca204d57aa3b usage 0%
[2024-03-15T16:29:31.227416Z] 5c902731 || 2024-03-15 16:29:31,227: DEBUG: gpu_idle_timeout: GPU-b805d632-775b-c673-fe68-26b26996cd09 usage 1%
[2024-03-15T16:29:34.247994Z] 5c902731 || 2024-03-15 16:29:34,247: DEBUG: gpu_idle_timeout: GPU-a5b02c30-9c95-cb81-e41e-ca204d57aa3b usage 0%
[2024-03-15T16:29:34.248037Z] 5c902731 || 2024-03-15 16:29:34,247: DEBUG: gpu_idle_timeout: GPU-b805d632-775b-c673-fe68-26b26996cd09 usage 1%
[2024-03-15T16:29:34.248048Z] 5c902731 || 2024-03-15 16:29:34,247: ERROR: gpu_idle_timeout: usage for all GPUs: ['GPU-a5b02c30-9c95-cb81-e41e-ca204d57aa3b', 'GPU-b805d632-775b-c673-fe68-26b26996cd09'] was below threshhold 20% for last 21 seconds. Killing process.
[2024-03-15T16:29:34.248059Z] 5c902731 || 2024-03-15 16:29:34,247: ERROR: gpu_idle_timeout: process still alive, maybe hung, killing.
[2024-03-15T16:29:35.885282Z] 5c902731 || ERROR: crashed: resources failed with non-zero exit code: container failed with non-zero exit code: 1 (exit code 1)
[2024-03-15T16:29:35.899668Z]          || ERROR: Trial 9 (Experiment 9) was terminated: allocation failed: resources failed with non-zero exit code: container failed with non-zero exit code: 1 (exit code 1)
```
