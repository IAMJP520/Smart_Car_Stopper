#pragma once
#include <lvgl.h>

#ifdef __cplusplus
extern "C" {
#endif

// 흑백 심플 HUD 화면 생성 + 로드
void hud_bw_show(void);

// 방향 표시 스위치: "LEFT" / "RIGHT" / "STRAIGHT"
void hud_bw_set_dir(const char* dir);

// 경로선 업데이트(옵션): 화면 좌표 lv_point_t 배열
void hud_bw_set_path(const lv_point_t* pts, uint16_t npts);

// 현재 속도(km/h) 표시
void hud_bw_set_speed(int speed_kmh);

#ifdef __cplusplus
}
#endif
