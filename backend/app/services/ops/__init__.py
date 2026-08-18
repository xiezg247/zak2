"""运维任务域：定时任务编排、同步 runner 与调度基础设施。

包含任务实现（sync_*/prefetch_*/warm_*/fill_* 等）、编排（catalog/runners/
scheduler/enqueue）与运行时基础设施（arq_jobs/embedded_scheduler/scheduler_defaults/
scheduler_lock/bars_lock）。

仅存放叶子模块，不在此重导出，避免循环导入。
"""
