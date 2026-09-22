// Copyright (c) 2025 by Rockchip Electronics Co., Ltd. All Rights Reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.


#ifndef _RKNN_DEMO_INTERNVL3_VISION_UTILS_H_
#define _RKNN_DEMO_INTERNVL3_VISION_UTILS_H_

#include "rknn3_api.h"
#include "common.h"


typedef struct {
    rknn3_context rknn_ctx;
    rknn3_input_output_num io_num;
    rknn3_tensor* inputs;
    rknn3_tensor* outputs;

    int model_channel;
    int model_height;
    int model_width;

    uint32_t* embeds_shape;
    uint32_t embeds_ndims;
} rknn_internvl3_vision_context;

int init_internvl3_vision(rknn_internvl3_vision_context* vision_ctx, const char* model_path, const char* weight_path, uint32_t core_mask);

int release_internvl3_vision(rknn_internvl3_vision_context* vision_ctx);

int inference_internvl3_vision(rknn_internvl3_vision_context* vision_ctx, image_buffer_t* img, float16* img_embeds);

#endif //_RKNN_DEMO_INTERNVL3_VISION_UTILS_H_