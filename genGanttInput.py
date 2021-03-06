# To parse the json Log into control messages and others
import json
import sys

LAST_STAGE_COMPLETE_TIME = -1
MS_TO_NS = 1000000
DRIVER = 0

class Executor:
    def __init__(self, executor_id, core_num, calibrate_delta):
        self.executorId = executor_id
        self.cores = core_num
        self.calibrate_delta = calibrate_delta
        # driver_clock + calibrate_delta = executor_clock, need to be calibrated.
        # i.e, executor_clock - calibrate_delta = "driver_clock"


class CompletedStage:
    # handle taskCompletionEvents
    def __init__(self, jlog):
        info = jlog["Stage Info"]
        self.id = int(info["Stage ID"])

        self.submission_ts = float(info["Submission Time"]) * MS_TO_NS  # ms -> ns
        print "minSubmission:{}".format(self.submission_ts)

        self.completion_ts = float(info["Completion Time"]) * MS_TO_NS  # ms -> ns
        print "minCompletion:{}".format(self.completion_ts)

        self.num_tasks = int(info["Number of Tasks"])
        self.broadcast_start_ts = float(jlog["BroadcastStartsTime"]) * MS_TO_NS
        self.broadcast_end_ts = float(jlog["BroadcastEndsTime"]) * MS_TO_NS
        self.destory_broadcast_start_ts = float(jlog["DestroyBroadcastStartsTime"]) * MS_TO_NS
        self.destory_broadcast_end_ts = float(jlog["DestroyBroadcastEndsTime"]) * MS_TO_NS
        self.update_weight_start_ts = float(jlog["updateWeightOnDriverStartsTime"]) * MS_TO_NS
        self.update_weight_end_ts = float(jlog["updateWeightOnDriverEndsTime"]) * MS_TO_NS
        self.judge_converge_start_ts = float(jlog["JudgeConvergeStartsTime"]) * MS_TO_NS
        self.judge_converge_end_ts = float(jlog["JudgeConvergeEndsTime"]) * MS_TO_NS
        
        self.send_broadcast_task_bin = float(jlog["BroadcastTaskBinEnds"]) * MS_TO_NS 
        # the time when driver starts to broadcast task binary

        self.last_completion_ts = self.submission_ts
        global LAST_STAGE_COMPLETE_TIME
        if LAST_STAGE_COMPLETE_TIME > 0:
            self.last_completion_ts = LAST_STAGE_COMPLETE_TIME
        LAST_STAGE_COMPLETE_TIME = self.completion_ts

        self.parents = list()  # store the parent stageIds
        for parent in jlog["Stage Info"]["Parent IDs"]:
            self.parents.append(int(parent))


class ProcessedStage:
    # stages that have been processed, have start_time and end_time aligned with those on driver.
    def __init__(self, completed_stage):        
        self.workers = dict()  # which thread has been involved in the computation of this stage
        self.schedule = list()  # stores ScheduledTask
        self.stage_info = completed_stage


class SubmittedStage:
    def __init__(self, jlog):
        info = jlog["Stage Info"]
        self.id = int(info["Stage ID"])
        self.num_tasks = int(info["Number of Tasks"])
        self.parents = list()  # store the parent stageIds

        for parent in info["Parent IDs"]:
            self.parents.append(int(parent))


class Task:
    def __init__(self, jlog):
        assert jlog["Event"] == "SparkListenerTaskEnd"

        # log on driver
        taskinfo = jlog["Task Info"]
        metrics = jlog["Task Metrics"]
        self.driver_send_rpc_ts = float(jlog["driverLanuchTime"]) * MS_TO_NS

        self.stageId = int(jlog["Stage ID"])
        self.executorId = int(taskinfo["Executor ID"])
        self.launch_time_ts = float(taskinfo["Launch Time"]) * MS_TO_NS
        self.finish_time_ts = float(taskinfo["Finish Time"]) * MS_TO_NS
        self.getting_result_time_ts = float(taskinfo["Getting Result Time"]) * MS_TO_NS

        self.shuffle_write = float(metrics["Shuffle Write Metrics"]["Shuffle Write Time"])  # already nanoseconds
        self.shuffle_read = float(metrics["Shuffle Read Metrics"]["Fetch Wait Time"]) * MS_TO_NS
        self.jvm_gc_time = float(metrics["JVM GC Time"]) * MS_TO_NS

        self.result_serialize = float(metrics["Result Serialization Time"]) * MS_TO_NS
        self.executor_deserialize = float(metrics["Executor Deserialize Time"]) * MS_TO_NS
        self.executor_run_time = float(metrics["Executor Run Time"]) * MS_TO_NS

        # log on executor
        self.task_decode_taskdesc_start_ts = float(jlog["DecodeStartsTime"]) * MS_TO_NS
        self.task_decode_taskdesc_end_ts = float(jlog["DecodeTaskDescEndsTime"]) * MS_TO_NS
        self.task_executor_lanuch_start_ts = float(jlog["ExecutorLanuchTaskTime"]) * MS_TO_NS
        self.task_deserialize_start_ts = float(jlog["taskDeserializeStarts"]) * MS_TO_NS
        self.task_deserialize_end_ts = float(jlog["taskDeserializeEnds"]) * MS_TO_NS
        self.task_run_start_ts = float(jlog["taskRunStarts"]) * MS_TO_NS

        self.executor_deserize_start_ts = float(jlog["ExecutorDeserialStarts"]) * MS_TO_NS
        self.executor_deserize_end_ts = float(jlog["ExecutorDeserialEnds"]) * MS_TO_NS

        self.task_run_end_ts = float(jlog["taskRunEnds"]) * MS_TO_NS
        self.task_result_serialize_start_ts = float(jlog["taskResultSerialStarts"]) * MS_TO_NS
        self.task_result_serialize_end_ts = float(jlog["taskResultSerialEnds"]) * MS_TO_NS
        self.task_result_serialize2_start_ts = float(jlog["taskResultSerial2Starts"]) * MS_TO_NS
        self.task_result_serialize2_end_ts = float(jlog["taskResultSerial2Ends"]) * MS_TO_NS
        self.task_put_result_into_local_blockmanager_start_ts = float(
            jlog["taskPutResultIntoLocalBlockMangerStarts"]) * MS_TO_NS
        self.task_put_result_into_local_blockmanager_end_ts = float(
            jlog["taskPutResultIntoLocalBlockMangerEnds"]) * MS_TO_NS

        self.input_map_start_ts = float(jlog["logInputMapStart"]) * MS_TO_NS
        self.input_map_end_ts = float(jlog["logInputMapEnd"]) * MS_TO_NS
        self.sample_filter_start_ts = float(jlog["logSampleFilterStart"]) * MS_TO_NS
        self.sample_filter_end_ts = float(jlog["logSampleFilterEnd"]) * MS_TO_NS
        self.seq_op_start_ts = float(jlog["logSeqOpStart"]) * MS_TO_NS
        self.seq_op_end_ts = float(jlog["logSeqOpEnd"]) * MS_TO_NS
        self.map_partition_with_index_start_ts = float(jlog["logMapPartitionWithIndexStart"]) * MS_TO_NS
        self.map_partition_with_index_end_ts = float(jlog["logMapPartitionWithIndexEnd"]) * MS_TO_NS
        self.com_op_start_ts = float(jlog["logCombOpStart"]) * MS_TO_NS
        self.com_op_end_ts = float(jlog["logCombOpEnd"]) * MS_TO_NS

        self.get_broadcast_bin_start = float(jlog["getBroadcastBinaryStart"]) * MS_TO_NS
        self.driver_send_task_desc_time = float(jlog["driverSendTaskDescTime"]) * MS_TO_NS
        self.executor_get_task_desc_time = float(jlog["ExecutorGetTaskDescTime"]) * MS_TO_NS
        self.task_end_send_result_via_RPC_time = float(jlog["taskEndSendResultViaRPCTime"]) * MS_TO_NS
        self.driver_get_result_via_RPC = float(jlog["DirverGetResultViaRPCTime"]) * MS_TO_NS
        self.driver_get_result_start_ts = float(jlog["driverGetResultStartTime"]) * MS_TO_NS
        self.driver_get_result_end_ts = float(jlog["driverGetResultEndTime"]) * MS_TO_NS
        

    def deserialize_executor_duration(self):
        return self.executor_deserize_end_ts - self.executor_deserize_start_ts

    def task_runner_duration(self):
        return self.task_result_serialize_start_ts - self.executor_deserize_start_ts

    def executor_duration(self):
        # time for running in the executor
        # include decode the task description, taskRunner time, serialize results,
        # and putResultIntoLocalBlockManger
        return self.task_put_result_into_local_blockmanager_end_ts - self.task_decode_taskdesc_start_ts

    def computing_duration(self):
        return self.executor_duration() - self.shuffle_read - self.shuffle_write - self.deserialize_executor_duration()

    def get_result_duration(self):
        if self.getting_result_time_ts == 0:
            return 0
        else:
            assert self.finish_time_ts > self.getting_result_time_ts
            return self.finish_time_ts - self.getting_result_time_ts

    def total_duration(self):
        # include scheduler delay, executor_duration, driver getting result
        return self.finish_time_ts - self.launch_time_ts

    def scheduler_delay(self):
        res = self.total_duration() - self.executor_duration() - self.get_result_duration()
        assert res > 0
        return res


class ScheduledTask:
    # tasks whose time are rescheduled according to the driver
    def __init__(self, task, start_time, end_time, thread_id):
        self.task = task
        self.start_time = start_time
        self.end_time = end_time
        self.thread_id = thread_id


class Thread:
    def __init__(self, thread_id, index, busy_until):
        self.thread_id = thread_id
        self.index = index
        self.busy_until = busy_until


class SparkState:
    def __init__(self, default_cores, calibrate_time):
        self.executors = dict()  # executorId --> Executor
        self.threads = dict()  # executorId --> list[Thread]
        self.submitted = dict()  # stageId --> SubmittedStage, stages just submitted, not all tasks are seen
        self.completed = dict()  # stageId --> CompletedStage
        self.processed = dict()  # stageId --> ProcessedStage
        self.skipped = dict()  # stageId --> -1. record skipped stages

        self.task_queue = list()  # a list of tasks
        self.prev_thread_id = 0  # DRIVER is 0
        self.executor_core_num = default_cores
        self.calibrate_time = calibrate_time

    def generate_thread_id(self):  # logically it is thread Id
        self.prev_thread_id += 1
        return self.prev_thread_id

    def add_executor(self, executor):
        assert not executor.executorId in self.executors
        # note that the number of cores should have been set in the executors
        # but here we use the one specified here
        # the executor should have a executorId
        executor_id = executor.executorId
        self.executors[executor_id] = executor

        threads_list = list()
        for i in range(self.executor_core_num):
            threads_list.append(Thread(self.generate_thread_id(), i, 0))
        # what is the index used for?
        # the executorId here is a global one, say we have 10 machines,
        # each with 8 cores, then the executorId ranges from 1 to 80, Driver is 0.

        self.threads[executor_id] = threads_list

    def submit_stage(self, submitted_stage):
        stage_id = submitted_stage.id
        assert stage_id not in self.submitted
        assert stage_id not in self.skipped

        for parent in submitted_stage.parents:
            if parent not in self.processed:
                self.skipped[parent] = -1

        self.submitted[stage_id] = submitted_stage

    def complete_stage(self, completed_stage):
        stage_id = completed_stage.id
        assert stage_id in self.submitted
        assert stage_id not in self.completed
        assert stage_id not in self.skipped

        submitted_stage = self.submitted.pop(stage_id, None)  # remove the stage from submitted
        self.completed[stage_id] = completed_stage

        if len(self.submitted) == 0:
            self.schedule_tasks()

    def schedule_tasks(self):
        # schedule all the tasks and stages, align the time
        task_num = 0
        for stage in self.completed:
            task_num += self.completed[stage].num_tasks

        assert len(self.task_queue) == task_num

        # sort the task by lanuch_ts, note that this time is one driver.
        self.task_queue.sort(key=lambda x: x.launch_time_ts)  # sort in place

        for stage_id in self.completed:
            stage = self.completed[stage_id]
            assert stage_id not in self.processed
            self.processed[stage_id] = ProcessedStage(stage)

        self.completed.clear()

        processed_stages = self.processed  # processed stages, constructed from completed stages

        for task in self.task_queue:
            stage = processed_stages[task.stageId]

            executor_id = task.executorId

            # shipping_delay = self.delay_split * task.scheduler_delay()
            # not using shipping delay anymore, directly use executorTime - calibrateTime
            task_duration = task.executor_duration()
            start_time = task.executor_get_task_desc_time - self.calibrate_time[executor_id]
            end_time = start_time + task_duration  # the time when getting result starts

            available_threads = filter(lambda x: x.busy_until < start_time, self.threads[task.executorId])

            # why we want to use the most recently one? This is not correct but a assumption.
            # because two cores have no strong connections, since they are logical concepts
            to_use_thread = max(lambda x: x.busy_until, available_threads)
            if len(to_use_thread) == 0:
                print "No thread available now, consider change the delay-split"
                exit()
            to_use_thread_x = to_use_thread[0]
            to_use_thread_x.busy_until = end_time
            stage.workers[to_use_thread_x.thread_id] = -1  # mean this thread is in use now.

            scheduled_task = ScheduledTask(task, start_time, end_time, to_use_thread_x.thread_id)
            stage.schedule.append(scheduled_task)

        self.processed.update(processed_stages)

        del self.task_queue[:]
        self.completed.clear()
        assert len(self.task_queue) == 0
        assert len(self.completed) == 0

    def add_task(self, task):
        # check whether we need to add a new executor
        if task.executorId not in self.executors:
            executor = Executor(task.executorId, self.executor_core_num, self.calibrate_time[task.executorId])
            self.add_executor(executor)

        self.task_queue.append(task)

    def read_json(self, inf):
        for line in open(inf):
            jlog = json.loads(line)
            eventType = jlog["Event"]
            if eventType == "SparkListenerExecutorAdded":
                executorId = int(jlog["Executor ID"])
                core_nums = int(jlog["Executor Info"]["Total Cores"])

                self.add_executor(Executor(executorId, core_nums, self.calibrate_time[executorId]))
            elif eventType == "SparkListenerTaskEnd":
                self.add_task(Task(jlog))
            elif eventType == "SparkListenerStageSubmitted":
                self.submit_stage(SubmittedStage(jlog))
            elif eventType == "SparkListenerStageCompleted":
                self.complete_stage(CompletedStage(jlog))
            else:
                pass

    def write_logs(self):
        for stageId in self.processed:
            stage = self.processed[stageId]
            stage_info = stage.stage_info
            op = stage_info.id

            if stage_info.broadcast_start_ts > 0:
                write_duration(DRIVER, stage_info.broadcast_start_ts,
                               stage_info.broadcast_end_ts - stage_info.broadcast_start_ts, "Broadcast", op)
            if stage_info.destory_broadcast_start_ts > 0:
                write_duration(DRIVER, stage_info.destory_broadcast_start_ts,
                               stage_info.destory_broadcast_end_ts - stage_info.destory_broadcast_start_ts, "DestoryBroadcast",
                               op)
            if stage_info.update_weight_start_ts > 0:
                write_duration(DRIVER, stage_info.update_weight_start_ts,
                               stage_info.update_weight_end_ts - stage_info.update_weight_start_ts, "UpdateWeight", op)

            if stage_info.judge_converge_start_ts > 0:
                write_duration(DRIVER, stage_info.judge_converge_start_ts,
                               stage_info.judge_converge_end_ts - stage_info.judge_converge_start_ts, "JudgeConverge", op)

            for scheduled in stage.schedule:
                task = scheduled.task
                worker = scheduled.thread_id
                send_ts = task.driver_send_task_desc_time
                recv_ts = scheduled.start_time
                local_executor_delta = self.calibrate_time[task.executorId]

                local_start = task.task_deserialize_start_ts
                # driver send RPC to executors, that you can start now
                write_control(DRIVER, send_ts, worker, recv_ts)

                if task.task_decode_taskdesc_end_ts - task.task_decode_taskdesc_start_ts > 0:
                    write_duration(worker, task.task_decode_taskdesc_start_ts - local_executor_delta,
                                   task.task_decode_taskdesc_end_ts - task.task_decode_taskdesc_start_ts,
                                   "DecodeDesc", op)

                # task deserize and executor deserize
                write_duration(worker, task.task_deserialize_start_ts - local_executor_delta,
                               task.executor_deserize_end_ts - task.task_deserialize_start_ts,
                               "Deserialization", op)

                start_read = task.executor_deserize_end_ts - local_executor_delta
                if task.shuffle_read > 0:
                    write_duration(worker, start_read, task.shuffle_read,
                                   "ShuffleRead", op)

                start_task_execute = start_read + task.shuffle_read;

                write_duration(worker, start_task_execute, task.computing_duration(),
                               "Computing", op)

                start_shuffle_write = start_task_execute + task.computing_duration();
                if task.shuffle_write > 0:
                    write_duration(worker, start_shuffle_write, task.shuffle_write,
                                   "ShuffleWrite", op)

                write_duration(worker, task.task_result_serialize_start_ts - local_executor_delta,
                               task.task_result_serialize_end_ts - task.task_result_serialize_start_ts,
                               "Serialization", op)

                write_duration(worker, task.task_result_serialize2_start_ts - local_executor_delta,
                               task.task_result_serialize2_end_ts - task.task_result_serialize2_start_ts,
                               "Serialization", op)

                write_duration(worker, task.task_put_result_into_local_blockmanager_start_ts - local_executor_delta,
                               task.task_put_result_into_local_blockmanager_end_ts - task.task_put_result_into_local_blockmanager_start_ts,
                               "PuttingIntoBlockManager", op)

                # transformations
                # if task.seq_op_start_ts > 0:
                #     write_duration(worker, task.seq_op_start_ts + recv_ts - local_start,
                #                    task.seq_op_end_ts - task.seq_op_start_ts, "SeqOp", op)

                # if task.map_partition_with_index_start_ts > 0:
                #     write_duration(worker, task.map_partition_with_index_start_ts + recv_ts - local_start,
                #                    task.map_partition_with_index_end_ts - task.map_partition_with_index_start_ts,
                #                    "MapPartitionWithIndex", op)

                # if task.com_op_start_ts > 0:
                #     write_duration(worker, task.com_op_start_ts + recv_ts - local_start,
                #                    task.com_op_end_ts - task.com_op_start_ts, "CombOp", op)

                # if task.input_map_start_ts > 0:
                #     write_duration(worker, task.input_map_start_ts + recv_ts - local_start,
                #                    task.input_map_end_ts - task.input_map_start_ts, "InputMap", op)

                # if task.sample_filter_start_ts > 0:
                #     write_duration(worker, task.sample_filter_start_ts + recv_ts - local_start,
                #                    task.sample_filter_end_ts - task.sample_filter_start_ts, "Sample", op)

                # communication edge for sending back the result
                send_ts = task.task_end_send_result_via_RPC_time - local_executor_delta
                recv_ts = task.driver_get_result_via_RPC
                write_control(worker, send_ts, DRIVER, recv_ts)
                # Before recv_ts is the driver time when executor starts to run.
                # if task.getting_result_time_ts == 0:
                #     recv_ts = task.finish_time_ts
                # else:
                #     recv_ts = task.getting_result_time_ts
                # # notify the driver that task has been finished, you can get the results.
                # write_control(worker, send_ts, DRIVER, recv_ts)
                # # if we have it, emit a getting result activity at the driver

                if not task.getting_result_time_ts == 0:
                    write_duration(DRIVER, task.driver_get_result_start_ts, task.driver_get_result_end_ts - task.driver_get_result_start_ts, "GettingResult", op)


def write_duration(thread_id, start_ts, duration, eventType, operator):
    print "activityType:{}=start_ts:{}=duration:{}=workerId:{}=stageId:{}".format(eventType, start_ts, duration,
                                                                                  thread_id, operator)


def write_control(sender, send_ts, receiver, recv_ts):
    print "activityType:ControlMessage=sender:{}=send_ts:{}=receiver:{}=recv_ts:{}".format(sender, send_ts, receiver,
                                                                                           recv_ts)


def convert(inf, core_num, executor_num, calibrate_file):
    executor_calibrate = [0] * (executor_num + 1)
    for line in open(calibrate_file):
        if line.startswith("#"):
            continue
        else:
            exe_id, min_x, max_x = line.strip().split()
            executor_calibrate[int(exe_id)] = float(min_x) * MS_TO_NS # default use the min_x

    ss = SparkState(core_num, executor_calibrate)

    ss.read_json(inf)
    ss.write_logs()


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print "python _.py inf executor_cores executor_num calibrate_file"
        exit()
    inf = sys.argv[1]
    executor_cores = int(sys.argv[2])
    executor_num = int(sys.argv[3])
    calibrate_file = sys.argv[4]
    # delay_split = float(sys.argv[3])

    convert(inf, executor_cores, executor_num, calibrate_file)
