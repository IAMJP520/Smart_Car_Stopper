#include "hud_bw.h"
#include <string.h>
#include "arrow_imgs.h"
LV_IMG_DECLARE(left_arrow_img);


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
static lv_obj_t* g_img_arrow = NULL;

// ---------- 컬러 및 스타일 ----------
#define HUD_COLOR_WHITE  lv_color_white()
#define HUD_COLOR_BG     lv_color_black()
#define HUD_COLOR_ACCENT lv_color_hex(0x00BFFF)  // DeepSkyBlue

static void style_line(lv_obj_t* line, uint16_t w) {
    lv_obj_set_style_line_width(line, w, 0);
    lv_obj_set_style_line_color(line, HUD_COLOR_ACCENT, 0);  // 강조 색상 적용
    lv_obj_set_style_line_opa(line, LV_OPA_COVER, 0);
}

static void style_label_white(lv_obj_t* l) {
    lv_obj_set_style_text_color(l, HUD_COLOR_WHITE, 0);
}

static void style_label_accent(lv_obj_t* l) {
    lv_obj_set_style_text_color(l, HUD_COLOR_ACCENT, 0);
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
static lv_obj_t* create_left_arrow_label(lv_obj_t* parent) {
    lv_obj_t* label = lv_label_create(parent);
    lv_label_set_text(label, LV_SYMBOL_LEFT);  // 또는 "←"
    lv_obj_set_style_text_font(label, LV_FONT_DEFAULT, 0);
    lv_obj_set_style_text_color(label, HUD_COLOR_ACCENT, 0);
    lv_obj_align(label, LV_ALIGN_CENTER, 0, 10);  // 중앙 위치 조정
    return label;
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
    static lv_point_t base[] = { {20,200}, {300,200} };
    g_ground = lv_line_create(parent);
    lv_line_set_points(g_ground, base, 2);
    style_line(g_ground, 2);

    // 눈금 (짧은 수직선 여러 개)
    /*for (int x = 40; x <= 280; x += 40) {
        static lv_point_t tick[2];
        lv_obj_t* t = lv_line_create(parent);
        tick[0].x = x; tick[0].y = 188;
        tick[1].x = x; tick[1].y = 196;
        lv_line_set_points(t, tick, 2);
        style_line(t, 2);
        (void)t; // 경고 억제
    }*/
}

// 좌우 차선 가이드라인
static void create_lane_guides(lv_obj_t* parent) {
    static lv_point_t left_line[] = { {76, 60}, {76, 180} };
    static lv_point_t right_line[] = { {244, 60}, {244, 180} };

    lv_obj_t* left = lv_line_create(parent);
    lv_obj_t* right = lv_line_create(parent);

    lv_line_set_points(left, left_line, 2);
    lv_line_set_points(right, right_line, 2);

    lv_obj_set_style_line_width(left, 2, 0);
    lv_obj_set_style_line_width(right, 2, 0);

    lv_obj_set_style_line_color(left, HUD_COLOR_ACCENT, 0);
    lv_obj_set_style_line_color(right, HUD_COLOR_ACCENT, 0);

    lv_obj_set_style_line_opa(left, LV_OPA_70, 0);
    lv_obj_set_style_line_opa(right, LV_OPA_70, 0);
}

// ---------- 공개 함수 ----------
void hud_bw_show(void)
{
    
    // 스크린 생성(검정)
    g_scr = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(g_scr, lv_color_black(), 0);
    lv_obj_set_style_bg_opa(g_scr, LV_OPA_COVER, 0);
    lv_obj_clear_flag(g_scr, LV_OBJ_FLAG_SCROLLABLE);
    
     // 바닥 가이드
    create_ground_guide(g_scr);
    create_lane_guides(g_scr);  // 바닥선 바로 위에 추가하면 자연스러움


    // 이미지 기반 왼쪽 화살표 (처음에는 숨겨둠)
    g_img_arrow = lv_img_create(g_scr);
    lv_img_set_src(g_img_arrow, &left_arrow_img);  // 초기화에 넣어도 되고 안 해도 됨
    lv_obj_align(g_img_arrow, LV_ALIGN_CENTER, 0, 10);
    lv_obj_add_flag(g_img_arrow, LV_OBJ_FLAG_HIDDEN);

    // 상단 방향 텍스트 (= 현재 지시)
    g_label_dir = lv_label_create(g_scr);
    style_label_accent(g_label_dir);
    lv_obj_set_style_text_letter_space(g_label_dir, 2, 0);
    lv_label_set_text(g_label_dir, "STRAIGHT");
    lv_obj_align(g_label_dir, LV_ALIGN_TOP_MID, 0, 6);

    // 화살표 3종
    g_left = create_left_arrow_label(g_scr);
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
    lv_obj_add_flag(g_img_arrow, LV_OBJ_FLAG_HIDDEN);  // 이미지도 숨김


    if (!dir || strlen(dir) < 1) return;

    // 방향 감지
    if (strstr(dir, "LEFT")) {
        lv_label_set_text(g_label_dir, dir);
        lv_img_set_src(g_img_arrow, &left_arrow_img);
        lv_obj_clear_flag(g_img_arrow, LV_OBJ_FLAG_HIDDEN);

    }
    else if (strstr(dir, "RIGHT")) {
        lv_label_set_text(g_label_dir, dir);
        lv_img_set_src(g_img_arrow, &right_arrow_img);
        lv_obj_clear_flag(g_img_arrow, LV_OBJ_FLAG_HIDDEN);

    }
    else {
        lv_label_set_text(g_label_dir, dir); // 예: "50m STRAIGHT"
        lv_img_set_src(g_img_arrow, &straight_arrow_img);
        lv_obj_clear_flag(g_img_arrow, LV_OBJ_FLAG_HIDDEN);

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
