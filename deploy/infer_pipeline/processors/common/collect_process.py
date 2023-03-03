#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Copyright (c) Huawei Technologies Co., Ltd. 2022-2022. All rights reserved.
Description: collect the mini batch, save the infer result and send the stop message to the manager module.
Author: MindX SDK
Create: 2022
History: NA
"""

import os
from collections import defaultdict
from ctypes import c_uint64
from multiprocessing import Manager

from deploy.infer_pipeline.data_type import StopData, ProcessData, ProfilingData
from deploy.infer_pipeline.framework import ModuleBase, InferModelComb
from deploy.infer_pipeline.utils import safe_list_writer, log

_RESULTS_SAVE_FILENAME = {
    InferModelComb.DET: 'det_results.txt',
    InferModelComb.REC: 'rec_results.txt',
    InferModelComb.DET_REC: 'pipeline_results.txt',
    InferModelComb.DET_CLS_REC: 'pipeline_results.txt'
}


class CollectProcess(ModuleBase):
    def __init__(self, args, msg_queue):
        super().__init__(args, msg_queue)
        self.without_input_queue = False
        self.image_sub_remaining = defaultdict(int)
        self.image_pipeline_res = defaultdict(list)
        self.infer_size = 0
        self.image_total = Manager().Value(c_uint64, 0)
        self.task_type = args.task_type
        self.save_filename = _RESULTS_SAVE_FILENAME[self.task_type]

    def init_self_args(self):
        super().init_self_args()

    def stop_handle(self, input_data):
        self.image_total.value = input_data.image_total

    def save_results(self):
        save_filename = os.path.join(self.infer_res_save_path, self.save_filename)
        safe_list_writer(self.image_pipeline_res, save_filename)
        log.info(f'save infer result to {save_filename} successfully')

    def result_handle(self, input_data):
        if input_data.image_id in self.image_sub_remaining:
            self.image_sub_remaining[input_data.image_id] -= len(input_data.infer_result)
            if not self.image_sub_remaining[input_data.image_id]:
                self.image_sub_remaining.pop(input_data.image_id)
                self.infer_size += 1
        else:
            remaining = input_data.sub_image_total - len(input_data.infer_result)
            if remaining:
                self.image_sub_remaining[input_data.image_id] = remaining
            else:
                self.infer_size += 1

        if self.task_type in (InferModelComb.DET_REC, InferModelComb.DET_CLS_REC):
            for result in input_data.infer_result:
                self.image_pipeline_res[input_data.image_name].append(
                    {"transcription": result[-1], "points": result[:-1]})
        elif self.task_type == InferModelComb.DET:
            self.image_pipeline_res[input_data.image_name] = input_data.infer_result[:]
        elif self.task_type == InferModelComb.REC:
            self.image_pipeline_res[input_data.image_name] = input_data.infer_result
        else:
            raise NotImplementedError

    def process(self, input_data):
        if isinstance(input_data, ProcessData):
            self.result_handle(input_data)
        elif isinstance(input_data, StopData):
            self.stop_handle(input_data)
        else:
            raise ValueError('unknown input data')

        if self.image_total.value and self.infer_size == self.image_total.value:
            self.save_results()
            self.send_to_next_module('stop')

    def stop(self):
        profiling_data = ProfilingData(module_name=self.module_name, instance_id=self.instance_id,
                                       device_id=self.device_id, process_cost_time=self.process_cost.value,
                                       send_cost_time=self.send_cost.value, image_total=self.image_total.value)
        self.msg_queue.put(profiling_data, block=False)
        self.is_stop = True
