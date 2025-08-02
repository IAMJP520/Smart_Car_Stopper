#include "hud_bw.h"
#include <string.h>

// ---------- 전역 핸들 ----------
static lv_obj_t* g_scr = NULL;
static lv_obj_t* g_label_dir = NULL;      // 상단 방향 텍스트
static lv_obj_t* g_line_path = NULL;      // 경로 폴리라인
static lv_obj_t* g_left = NULL;
static lv_obj_t* g_right = NULL;
static lv_obj_t* g_straight = NULL;
static lv_obj_t* g_speed_val = NULL;      // 큰 숫자
static lv_obj_t* g_speed_unit = NULL;     // "km/h"
static lv_obj_t* g_ground = NULL;         // 바닥선(도로 가이드)

// ---------- 공통 스타일 ----------
static void style_line(lv_obj_t* line, uint16_t w) {
    lv_obj_set_style_line_width(line, w, 0);
    lv_obj_set_style_line_color(line, lv_color_white(), 0);
    lv_obj_set_style_line_opa(line, LV_OPA_COVER, 0);
}
static void style_label_white(lv_obj_t* l) {
    lv_obj_set_style_text_color(l, lv_color_white(), 0);
}

// 큰 폰트 선택(사용 가능할 때만). 없으면 기본 폰트 사용.
static const lv_font_t* pick_big_font() {
#if LV_FONT_MONTSERRAT_48
    return &lv_font_montserrat_48;
#elif LV_FONT_MONTSERRAT_36
    return &lv_font_montserrat_36;
#elif LV_FONT_MONTSERRAT_32
    return &lv_font_montserrat_32;
#else
    return LV_FONT_DEFAULT;
#endif
}

// ---------- 화살표 생성(선 기반, 흑백) ----------
static lv_obj_t* create_left_arrow(lv_obj_t* parent) {
    static lv_point_t pts[] = { {210,120},{120,120},{120,92},{85,120},{120,148},{120,120} };
    lv_obj_t* L = lv_line_create(parent);
    lv_line_set_points(L, pts, sizeof(pts)/sizeof(pts[0]));
    style_line(L, 8);
    return L;
}
static lv_obj_t* create_right_arrow(lv_obj_t* parent) {
    static lv_point_t pts[] = { {110,120},{200,120},{200,92},{235,120},{200,148},{200,120} };
    lv_obj_t* R = lv_line_create(parent);
    lv_line_set_points(R, pts, sizeof(pts)/sizeof(pts[0]));
    style_line(R, 8);
    return R;
}
static lv_obj_t* create_straight_arrow(lv_obj_t* parent) {
    static lv_point_t pts[] = { {160,175},{160,78},{132,106},{160,78},{188,106} };
    lv_obj_t* S = lv_line_create(parent);
    lv_line_set_points(S, pts, sizeof(pts)/sizeof(pts[0]));
    style_line(S, 8);
    return S;
}

// 하단 바닥 가이드 라인(직선 + 작은 눈금)
static void create_ground_guide(lv_obj_t* parent) {
    // 메인 바닥선
    static lv_point_t base[] = { {20,190}, {300,190} };
    g_ground = lv_line_create(parent);
    lv_line_set_points(g_ground, base, 2);
    style_line(g_ground, 2);

    // 눈금 (짧은 수직선 여러 개)
    for (int x = 40; x <= 280; x += 40) {
        static lv_point_t tick[2];
        lv_obj_t* t = lv_line_create(parent);
        tick[0].x = x; tick[0].y = 188;
        tick[1].x = x; tick[1].y = 196;
        lv_line_set_points(t, tick, 2);
        style_line(t, 2);
        (void)t; // 경고 억제
    }
}

// ---------- 공개 함수 ----------
void hud_bw_show(void)
{
    // 스크린 생성(검정)
    g_scr = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(g_scr, lv_color_black(), 0);
    lv_obj_set_style_bg_opa(g_scr, LV_OPA_COVER, 0);
    lv_obj_clear_flag(g_scr, LV_OBJ_FLAG_SCROLLABLE);

    // 상단 방향 텍스트 (= 현재 지시)
    g_label_dir = lv_label_create(g_scr);
    style_label_white(g_label_dir);
    lv_obj_set_style_text_letter_space(g_label_dir, 2, 0);
    lv_label_set_text(g_label_dir, "STRAIGHT");
    lv_obj_align(g_label_dir, LV_ALIGN_TOP_MID, 0, 6);

    // 화살표 3종
    g_left     = create_left_arrow(g_scr);
    g_right    = create_right_arrow(g_scr);
    g_straight = create_straight_arrow(g_scr);

    // 기본: 직진만 표시
    lv_obj_add_flag(g_left, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(g_right, LV_OBJ_FLAG_HIDDEN);
    lv_obj_clear_flag(g_straight, LV_OBJ_FLAG_HIDDEN);

    // 경로 폴리라인(옵션)
    g_line_path = lv_line_create(g_scr);
    style_line(g_line_path, 3);
    lv_obj_add_flag(g_line_path, LV_OBJ_FLAG_HIDDEN);

    // 바닥 가이드
    create_ground_guide(g_scr);

    // 속도 표시(큰 숫자 + 단위). 하단 중앙.
    g_speed_val = lv_label_create(g_scr);
    style_label_white(g_speed_val);
    lv_obj_set_style_text_font(g_speed_val, pick_big_font(), 0);
    lv_label_set_text(g_speed_val, "80");           // 초기 표시값
    lv_obj_align(g_speed_val, LV_ALIGN_BOTTOM_MID, -18, -10);

    g_speed_unit = lv_label_create(g_scr);
    style_label_white(g_speed_unit);
#if LV_FONT_MONTSERRAT_16
    lv_obj_set_style_text_font(g_speed_unit, &lv_font_montserrat_16, 0);
#endif
    lv_label_set_text(g_speed_unit, "km/h");
    lv_obj_align_to(g_speed_unit, g_speed_val, LV_ALIGN_OUT_RIGHT_MID, 6, 6);

    // 로드
    lv_scr_load(g_scr);
}

// 수정된 버전: "LEFT", "RIGHT", "STRAIGHT", 또는 "30m LEFT" 식 입력 지원
void hud_bw_set_dir(const char* dir)
{
    if(!g_scr) return;

    // 모두 숨김
    lv_obj_add_flag(g_left, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(g_right, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(g_straight, LV_OBJ_FLAG_HIDDEN);

    if (!dir || strlen(dir) < 1) return;

    // 방향 감지
    if (strstr(dir, "LEFT")) {
        lv_label_set_text(g_label_dir, dir);
        lv_obj_clear_flag(g_left, LV_OBJ_FLAG_HIDDEN);
    }
    else if (strstr(dir, "RIGHT")) {
        lv_label_set_text(g_label_dir, dir);
        lv_obj_clear_flag(g_right, LV_OBJ_FLAG_HIDDEN);
    }
    else {
        lv_label_set_text(g_label_dir, dir); // 예: "50m STRAIGHT"
        lv_obj_clear_flag(g_straight, LV_OBJ_FLAG_HIDDEN);
    }
}


void hud_bw_set_path(const lv_point_t* pts, uint16_t npts)
{
    if(!g_scr || !pts || npts < 2) {
        if(g_line_path) lv_obj_add_flag(g_line_path, LV_OBJ_FLAG_HIDDEN);
        return;
    }
    lv_line_set_points(g_line_path, pts, npts);
    lv_obj_clear_flag(g_line_path, LV_OBJ_FLAG_HIDDEN);
}

void hud_bw_set_speed(int speed_kmh)
{
    if(!g_scr || !g_speed_val) return;
    char buf[8];
    if (speed_kmh < 0) speed_kmh = 0;
    if (speed_kmh > 999) speed_kmh = 999;
    lv_snprintf(buf, sizeof(buf), "%d", speed_kmh);
    lv_label_set_text(g_speed_val, buf);
}
