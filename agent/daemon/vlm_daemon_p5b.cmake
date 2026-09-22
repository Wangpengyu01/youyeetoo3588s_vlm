# P5b vlm_daemon — InternVL SDK sources + model-zoo utils (included from rknn3_session_test_demo).
if(TARGET vlm_daemon)
  return()
endif()

get_filename_component(RKNN3_RUNTIME_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../.." ABSOLUTE)
get_filename_component(RKNN_ROOT "${RKNN3_RUNTIME_ROOT}/.." ABSOLUTE)
set(MODEL_ZOO "${RKNN_ROOT}/rknn3-model-zoo")
set(INTERNVL_CPP "${MODEL_ZOO}/examples/InternVLM/cpp")

if(NOT EXISTS "${INTERNVL_CPP}/internvl3.cc")
  message(FATAL_ERROR "Missing InternVLM demo at ${INTERNVL_CPP}")
endif()

if(NOT TARGET timeutils)
  add_subdirectory("${MODEL_ZOO}/3rdparty" "${CMAKE_BINARY_DIR}/model_zoo_3rdparty")
  add_subdirectory("${MODEL_ZOO}/utils" "${CMAKE_BINARY_DIR}/model_zoo_utils")
endif()

include_directories(
  "${INTERNVL_CPP}"
  "${INTERNVL_CPP}/llm"
  "${INTERNVL_CPP}/vision"
  "${MODEL_ZOO}/utils/image_utils/include"
  "${MODEL_ZOO}/utils/file_utils/include"
  "${MODEL_ZOO}/utils/time_utils/include"
)

add_executable(vlm_daemon
  src/vlm_daemon.cpp
  src/vlm_internvl_bridge.cpp
  "${INTERNVL_CPP}/internvl3.cc"
  "${INTERNVL_CPP}/llm/rknn_internvl3_llm.cc"
  "${INTERNVL_CPP}/vision/rknn_internvl3_vision.cc"
)

if(TOKENIZER_LIB)
  target_link_libraries(vlm_daemon
    ${RKNN3_API_LIB}
    ${TOKENIZER_LIB}
    timeutils
    imageutils
    fileutils
    pthread
    dl
  )
else()
  target_link_libraries(vlm_daemon
    ${RKNN3_API_LIB}
    timeutils
    imageutils
    fileutils
    pthread
    dl
  )
endif()
