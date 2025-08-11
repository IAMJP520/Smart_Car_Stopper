import sys
import math
from heapq import heappush, heappop
from collections import deque
from PyQt5.QtWidgets import (
    QApplication, QGraphicsScene, QGraphicsView, QGraphicsRectItem,
    QGraphicsSimpleTextItem, QGraphicsEllipseItem,
    QPushButton, QWidget, QVBoxLayout, QHBoxLayout, QGraphicsItem,
    QLineEdit, QLabel, QMessageBox, QGraphicsItemGroup, QFrame,
    QScrollArea, QSizePolicy
)
from PyQt5.QtGui import QBrush, QPainter, QPen, QColor, QPainterPath, QFont, QPixmap
from PyQt5.QtCore import Qt, QPointF, QRectF, QTimer

class RouteHUD(QFrame):
    """경로 안내 HUD 패널"""
    def __init__(self):
        super().__init__()
        self.setFixedWidth(300)
        self.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border: 2px solid #333;
                border-radius: 10px;
            }
            QLabel {
                color: #ffffff;
                font-size: 12px;
            }
            .title {
                color: #00ff88;
                font-size: 14px;
                font-weight: bold;
            }
            .distance {
                color: #ffaa00;
                font-size: 11px;
            }
            .instruction {
                color: #ffffff;
                font-size: 13px;
                font-weight: bold;
            }
            .waypoint {
                color: #88aaff;
                font-size: 12px;
            }
        """)
        
        self.layout = QVBoxLayout()
        self.layout.setSpacing(10)
        self.layout.setContentsMargins(15, 15, 15, 15)
        
        # 제목
        self.title = QLabel("🗺️ 경로 안내")
        self.title.setProperty("class", "title")
        self.title.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.title)
        
        # 전체 경로 정보
        self.route_info = QLabel("경로를 생성하세요")
        self.route_info.setProperty("class", "distance")
        self.route_info.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.route_info)
        
        # 구분선
        line1 = QFrame()
        line1.setFrameShape(QFrame.HLine)
        line1.setStyleSheet("color: #444;")
        self.layout.addWidget(line1)
        
        # 턴바이턴 지시사항 스크롤 영역
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: #333;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background-color: #666;
                border-radius: 4px;
            }
        """)
        
        self.instructions_widget = QWidget()
        self.instructions_layout = QVBoxLayout(self.instructions_widget)
        self.instructions_layout.setSpacing(8)
        
        self.scroll_area.setWidget(self.instructions_widget)
        self.layout.addWidget(self.scroll_area)
        
        # 웨이포인트 정보
        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setStyleSheet("color: #444;")
        self.layout.addWidget(line2)
        
        self.waypoints_info = QLabel("웨이포인트: 없음")
        self.waypoints_info.setProperty("class", "waypoint")
        self.layout.addWidget(self.waypoints_info)
        
        self.setLayout(self.layout)
        self.current_instructions = []

    def clear_instructions(self):
        """기존 지시사항 제거"""
        for i in reversed(range(self.instructions_layout.count())):
            child = self.instructions_layout.itemAt(i).widget()
            if child:
                child.deleteLater()
        self.current_instructions = []

    def add_instruction(self, step_num, direction, instruction, distance=""):
        """턴바이턴 지시사항 추가"""
        instruction_frame = QFrame()
        instruction_frame.setStyleSheet("""
            QFrame {
                background-color: #2a2a2a;
                border: 1px solid #444;
                border-radius: 5px;
                padding: 8px;
            }
        """)
        
        layout = QVBoxLayout(instruction_frame)
        layout.setSpacing(4)
        
        # 단계 번호와 방향
        header = QLabel(f"{step_num}. {direction}")
        header.setProperty("class", "instruction")
        layout.addWidget(header)
        
        # 지시사항
        inst_label = QLabel(instruction)
        inst_label.setWordWrap(True)
        layout.addWidget(inst_label)
        
        # 거리 정보
        if distance:
            dist_label = QLabel(distance)
            dist_label.setProperty("class", "distance")
            layout.addWidget(dist_label)
        
        self.instructions_layout.addWidget(instruction_frame)
        self.current_instructions.append(instruction_frame)

    def update_route_info(self, total_distance, waypoint_count):
        """전체 경로 정보 업데이트"""
        self.route_info.setText(f"총 거리: {total_distance:.0f}m\n경로 생성 완료")
        self.waypoints_info.setText(f"웨이포인트: {waypoint_count}개")

class ParkingLotUI(QWidget):
    SCENE_W, SCENE_H = 2000, 2000
    CELL = 30         # 셀 그리드(클수록 가볍고 경로는 각지됨)
    MARGIN = 10       # 장애물 팽창 여유(px)
    PATH_WIDTH = 6    # 경로 두께
    DRAW_DOTS = False # 경로 점 마커 표시 여부

    ENTRANCE = QPointF(200, 200)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("실내 주차장 UI (웨이포인트 기반 경로 안내 + HUD)")
        self.setGeometry(100, 100, 1500, 900)

        # 메인 레이아웃 (수평 분할)
        main_layout = QHBoxLayout()
        
        # 왼쪽: 지도 영역
        map_widget = QWidget()
        map_layout = QVBoxLayout(map_widget)
        
        self.scene = QGraphicsScene(0, 0, self.SCENE_W, self.SCENE_H)
        self.scene.setItemIndexMethod(QGraphicsScene.NoIndex)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setViewportUpdateMode(QGraphicsView.MinimalViewportUpdate)
        self.view.scale(0.5, 0.5)
        # 좌하단 원점
        self.view.scale(1, -1)
        self.view.translate(0, -self.SCENE_H)

        # UI: 웨이포인트 3개 입력(x,y). 비워두면 무시.
        self.le1 = QLineEdit(); self.le1.setPlaceholderText("예: 1300,925  (필수)")
        self.le2 = QLineEdit(); self.le2.setPlaceholderText("예: 1475,925  (선택)")
        self.le3 = QLineEdit(); self.le3.setPlaceholderText("예: 1475,1300 (선택)")
        self.btn_apply = QPushButton("경로 안내")
        self.btn_apply.clicked.connect(self.apply_route_from_inputs)

        row1 = QHBoxLayout(); row1.addWidget(QLabel("W1:")); row1.addWidget(self.le1)
        row2 = QHBoxLayout(); row2.addWidget(QLabel("W2:")); row2.addWidget(self.le2)
        row3 = QHBoxLayout(); row3.addWidget(QLabel("W3:")); row3.addWidget(self.le3)

        controls = QHBoxLayout()
        controls.addStretch(1); controls.addWidget(self.btn_apply)

        map_layout.addWidget(self.view)
        map_layout.addLayout(row1)
        map_layout.addLayout(row2) 
        map_layout.addLayout(row3)
        map_layout.addLayout(controls)

        # 오른쪽: HUD 패널
        self.hud = RouteHUD()

        # 메인 레이아웃에 추가
        main_layout.addWidget(map_widget, 3)  # 지도가 더 넓게
        main_layout.addWidget(self.hud, 1)    # HUD는 고정 폭
        
        self.setLayout(main_layout)

        # 레이어: 정적/경로 분리
        self.layer_static = QGraphicsItemGroup()
        self.layer_path = QGraphicsItemGroup()
        self.scene.addItem(self.layer_static)
        self.scene.addItem(self.layer_path)

        self.build_static_layout()
        self.build_occupancy()

    # ---------- 정적 레이아웃 ----------
    def add_block(self, x, y, w, h, color, label=""):
        r = QGraphicsRectItem(QRectF(x, y, w, h))
        r.setBrush(QBrush(color)); r.setPen(QPen(Qt.black))
        r.setParentItem(self.layer_static)
        if label:
            t = QGraphicsSimpleTextItem(label)
            t.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            t.setPos(x+5, y+h-20)
            t.setParentItem(self.layer_static)
        return r

    def add_hatched(self, x, y, w, h, edge=QColor("black"), fill=QColor(220, 20, 60, 90)):
        r = QGraphicsRectItem(QRectF(x, y, w, h))
        b = QBrush(fill); b.setStyle(Qt.BDiagPattern)
        r.setBrush(b); r.setPen(QPen(edge, 2))
        r.setParentItem(self.layer_static)
        t = QGraphicsSimpleTextItem("통행 불가")
        t.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        t.setPos(x+10, y+h-25)
        t.setParentItem(self.layer_static)

    def add_dot_label_static(self, p: QPointF, text: str, color=QColor("blue")):
        d = QGraphicsEllipseItem(p.x()-5, p.y()-5, 10, 10)
        d.setBrush(QBrush(color)); d.setPen(QPen(Qt.black))
        d.setParentItem(self.layer_static)
        t = QGraphicsSimpleTextItem(text)
        t.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        t.setPos(p.x()-20, p.y()+20)
        t.setParentItem(self.layer_static)

    def build_static_layout(self):
        c_dis = QColor("#f4a261"); c_ele = QColor("#2a9d8f")
        c_gen = QColor("#264653");  c_obs = QColor("#6c757d")
        c_emp = QColor("#ced4da");  c_io  = QColor("#e76f51")

        border = QGraphicsRectItem(0, 0, self.SCENE_W, self.SCENE_H)
        border.setPen(QPen(QColor("black"), 8))
        border.setParentItem(self.layer_static)

        base = [
            (0,1600,300,400,c_dis,"장애인"), (300,1600,300,400,c_dis,"장애인"),
            (600,1600,200,400,c_gen,"일반"), (800,1600,200,400,c_gen,"일반"),
            (1000,1600,200,400,c_gen,"일반"), (1200,1600,200,400,c_ele,"전기차"),
            (1400,1600,200,400,c_ele,"전기차"), (1600,1600,400,400,c_emp,"빈기둥"),
            (550,1050,800,300,c_obs,"장애물"), (1600,400,400,400,c_emp,"빈기둥"),
            (0,0,400,400,c_io,"입출차"),
        ]
        for x,y,w,h,c,l in base: self.add_block(x,y,w,h,c,l)
        for i in range(6): self.add_block(400+i*200, 400, 200, 400, c_gen, "일반")
        for i in range(4): self.add_block(1600, 800+i*200, 400, 200, c_gen, "일반")

        self.add_hatched(400, 0, 1600, 400)  # 하단 통행불가 밴드
        self.add_dot_label_static(self.ENTRANCE, "입구", QColor("blue"))

    # ---------- 점유맵 ----------
    def build_occupancy(self):
        W, H, C = self.SCENE_W, self.SCENE_H, self.CELL
        gx, gy = (W + C - 1) // C, (H + C - 1) // C  # ceil
        self.grid_w, self.grid_h = gx, gy
        self.occ = bytearray(gx * gy)  # 0=free, 1=blocked

        def idx(cx, cy): 
            return cy * gx + cx

        def block_rect(x, y, w, h):
            x0, y0 = max(0, x - self.MARGIN), max(0, y - self.MARGIN)
            x1, y1 = min(W, x + w + self.MARGIN), min(H, y + h + self.MARGIN)
            cx0, cy0 = int(x0 // C), int(y0 // C)
            cx1, cy1 = int((x1 - 1) // C), int((y1 - 1) // C)
            cx0 = max(0, min(cx0, gx - 1)); cx1 = max(0, min(cx1, gx - 1))
            cy0 = max(0, min(cy0, gy - 1)); cy1 = max(0, min(cy1, gy - 1))
            for cy in range(cy0, cy1 + 1):
                base = cy * gx
                for cx in range(cx0, cx1 + 1):
                    self.occ[base + cx] = 1

        # 막을 영역들
        block_rect(550,1050,800,300)     # 장애물
        block_rect(400,0,1600,400)       # 하단 통행불가 밴드
        # block_rect(0,0,400,400)        # 입구 차로는 열어둠
        block_rect(1600,400,400,400)     # 빈기둥
        block_rect(1600,1600,400,400)    # 빈기둥 상단
        block_rect(0,1600,300,400)       # 상단 장애인
        block_rect(300,1600,300,400)
        for i in range(6): block_rect(400 + i*200, 400, 200, 400)         # 하단 일반
        for i in range(4): block_rect(1600, 800 + i*200, 400, 200)        # 우측 일반
        block_rect(600,1600,200,400); block_rect(800,1600,200,400)        # 상단 일반/전기
        block_rect(1000,1600,200,400); block_rect(1200,1600,200,400)
        block_rect(1400,1600,200,400)

        self._occ_idx = idx

    # ---------- Grid <-> World ----------
    def clamp_point(self, p: QPointF):
        return QPointF(
            min(self.SCENE_W-1.0, max(0.0, p.x())),
            min(self.SCENE_H-1.0, max(0.0, p.y()))
        )

    def pt_to_cell(self, p: QPointF):
        cx = int(p.x() // self.CELL)
        cy = int(p.y() // self.CELL)
        cx = max(0, min(cx, self.grid_w - 1))
        cy = max(0, min(cy, self.grid_h - 1))
        return cx, cy

    def cell_to_pt_center(self, c):
        cx, cy = c
        return QPointF(cx * self.CELL + self.CELL / 2.0,
                       cy * self.CELL + self.CELL / 2.0)

    # ---------- 유틸: 자유셀 탐색 ----------
    def is_cell_free(self, cx, cy):
        if cx < 0 or cy < 0 or cx >= self.grid_w or cy >= self.grid_h:
            return False
        return self.occ[self._occ_idx(cx, cy)] == 0

    def find_nearest_free_cell_from_point(self, p: QPointF, max_radius_cells=30):
        """목표 셀이 막혀있을 때, 가장 가까운 자유셀(맨해튼 우선) 탐색."""
        sx, sy = self.pt_to_cell(p)
        if self.is_cell_free(sx, sy):
            return self.cell_to_pt_center((sx, sy))
        # BFS 레이어 확장
        for r in range(1, max_radius_cells+1):
            for dx in range(-r, r+1):
                for dy in (-r, r):
                    cx, cy = sx+dx, sy+dy
                    if self.is_cell_free(cx, cy):
                        return self.cell_to_pt_center((cx, cy))
            for dy in range(-r+1, r):
                for dx in (-r, r):
                    cx, cy = sx+dx, sy+dy
                    if self.is_cell_free(cx, cy):
                        return self.cell_to_pt_center((cx, cy))
        return self.cell_to_pt_center((sx, sy))  # 최후의 보정

    # ---------- A* (4방향) ----------
    def astar(self, start_pt: QPointF, goal_pt: QPointF):
        sx, sy = self.pt_to_cell(start_pt)
        gx, gy = self.pt_to_cell(goal_pt)
        W, H = self.grid_w, self.grid_h
        occ, idx = self.occ, self._occ_idx

        def inb(x,y): return 0<=x<W and 0<=y<H
        if not inb(sx,sy) or not inb(gx,gy): return None
        if occ[idx(sx,sy)] or occ[idx(gx,gy)]: return None

        nbr = [(1,0,1), (-1,0,1), (0,1,1), (0,-1,1)]
        def heur(x,y):  # Manhattan
            return abs(x-gx) + abs(y-gy)

        openh = []
        heappush(openh, (heur(sx,sy), 0, (sx,sy)))
        came = {}
        g = { (sx,sy): 0 }

        while openh:
            f, gc, (x,y) = heappop(openh)
            if (x,y) == (gx,gy):
                path = [(x,y)]
                while (x,y) in came:
                    x,y = came[(x,y)]
                    path.append((x,y))
                path.reverse()
                return path
            for dx,dy,cst in nbr:
                nx, ny = x+dx, y+dy
                if not inb(nx,ny): continue
                if occ[idx(nx,ny)]: continue
                ng = gc + cst
                if (nx,ny) not in g or ng < g[(nx,ny)]:
                    g[(nx,ny)] = ng
                    came[(nx,ny)] = (x,y)
                    heappush(openh, (ng + heur(nx,ny), ng, (nx,ny)))
        return None

    # ---------- 단순화 ----------
    def simplify_cells(self, cells):
        if not cells: return cells
        simp = [cells[0]]
        def norm(vx, vy):
            return (0 if vx==0 else (1 if vx>0 else -1),
                    0 if vy==0 else (1 if vy>0 else -1))
        for i in range(1, len(cells)-1):
            x0,y0 = simp[-1]
            x1,y1 = cells[i]
            x2,y2 = cells[i+1]
            if norm(x1-x0, y1-y0) == norm(x2-x1, y2-y1):
                continue
            simp.append(cells[i])
        if cells[-1] != simp[-1]:
            simp.append(cells[-1])
        return simp

    # ---------- 경로 분석 및 HUD 업데이트 ----------
    def analyze_route_and_update_hud(self, pts, waypoints):
        """경로를 분석해서 HUD에 턴바이턴 지시사항 생성"""
        self.hud.clear_instructions()
        
        if len(pts) < 2:
            return
        
        # 총 거리 계산
        total_distance = 0
        for i in range(len(pts) - 1):
            dx = pts[i+1].x() - pts[i].x()
            dy = pts[i+1].y() - pts[i].y()
            total_distance += math.sqrt(dx*dx + dy*dy)
        
        self.hud.update_route_info(total_distance, len(waypoints))
        
        # 주요 전환점 찾기 및 지시사항 생성
        step = 1
        current_waypoint_idx = 0
        
        self.hud.add_instruction(step, "🚗", "입구에서 출발", "시작점")
        step += 1
        
        # 경로의 주요 방향 변화 지점들 찾기
        directions = []
        for i in range(len(pts) - 1):
            dx = pts[i+1].x() - pts[i].x()
            dy = pts[i+1].y() - pts[i].y()
            
            if abs(dx) > abs(dy):
                direction = "동쪽" if dx > 0 else "서쪽"
            else:
                direction = "북쪽" if dy > 0 else "남쪽"
            directions.append(direction)
        
        # 방향 변화 지점에서 지시사항 생성
        current_dir = directions[0] if directions else "북쪽"
        segment_distance = 0
        
        for i, direction in enumerate(directions):
            dx = pts[i+1].x() - pts[i].x()
            dy = pts[i+1].y() - pts[i].y()
            segment_distance += math.sqrt(dx*dx + dy*dy)
            
            if direction != current_dir or i == len(directions) - 1:
                if segment_distance > 50:  # 50픽셀 이상의 구간만 표시
                    if direction != current_dir:
                        # 방향 전환 지시
                        if current_dir == "북쪽" and direction == "동쪽":
                            turn = "➡️ 우회전"
                        elif current_dir == "동쪽" and direction == "남쪽":
                            turn = "➡️ 우회전"
                        elif current_dir == "남쪽" and direction == "서쪽":
                            turn = "➡️ 우회전"
                        elif current_dir == "서쪽" and direction == "북쪽":
                            turn = "➡️ 우회전"
                        elif current_dir == "북쪽" and direction == "서쪽":
                            turn = "⬅️ 좌회전"
                        elif current_dir == "서쪽" and direction == "남쪽":
                            turn = "⬅️ 좌회전"
                        elif current_dir == "남쪽" and direction == "동쪽":
                            turn = "⬅️ 좌회전"
                        elif current_dir == "동쪽" and direction == "북쪽":
                            turn = "⬅️ 좌회전"
                        else:
                            turn = "🔄 방향 변경"
                        
                        self.hud.add_instruction(
                            step, turn, 
                            f"{direction}으로 이동",
                            f"약 {segment_distance:.0f}m"
                        )
                        step += 1
                    
                    current_dir = direction
                    segment_distance = 0
        
        # 웨이포인트 도달 지시사항
        for i, wp in enumerate(waypoints):
            self.hud.add_instruction(
                step, "📍", 
                f"웨이포인트 {i+1} 도달",
                f"좌표: ({wp.x():.0f}, {wp.y():.0f})"
            )
            step += 1
        
        # 최종 도착
        self.hud.add_instruction(step, "🏁", "목적지 도착", "주차 완료")

    # ---------- 경로 그리기(부드럽게, 장애물 근처는 직선) ----------
    def is_point_near_blocked(self, p: QPointF, r_cells=2):
        cx, cy = self.pt_to_cell(p)
        for dy in range(-r_cells, r_cells + 1):
            for dx in range(-r_cells, r_cells + 1):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < self.grid_w and 0 <= ny < self.grid_h:
                    if self.occ[self._occ_idx(nx, ny)]:
                        return True
        return False

    def draw_smooth_path(self, pts):
        if len(pts) < 2: return
        path = QPainterPath(); path.moveTo(pts[0])

        if len(pts) == 2:
            path.lineTo(pts[1])
        else:
            t = 0.35
            m1 = QPointF((pts[0].x()+pts[1].x())/2, (pts[0].y()+pts[1].y())/2)
            path.lineTo(m1)
            for i in range(1, len(pts)-1):
                p0, p1, p2 = pts[i-1], pts[i], pts[i+1]
                m_in  = QPointF(p1.x() + (p0.x()-p1.x())*t, p1.y() + (p0.y()-p1.y())*t)
                m_out = QPointF(p1.x() + (p2.x()-p1.x())*t, p1.y() + (p2.y()-p1.y())*t)
                if self.is_point_near_blocked(p1, r_cells=2) or \
                   self.is_point_near_blocked(m_in, r_cells=2) or \
                   self.is_point_near_blocked(m_out, r_cells=2):
                    path.lineTo(p1)
                else:
                    path.lineTo(m_in); path.quadTo(p1, m_out)
            path.lineTo(pts[-1])

        item = self.scene.addPath(
            path,
            QPen(QColor(255, 77, 77, 220), self.PATH_WIDTH, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        )
        item.setParentItem(self.layer_path)

        if self.DRAW_DOTS:
            for p in pts:
                dot = QGraphicsEllipseItem(p.x()-3, p.y()-3, 6, 6)
                dot.setBrush(QBrush(QColor(255, 77, 77, 230)))
                dot.setPen(QPen(Qt.NoPen))
                dot.setParentItem(self.layer_path)

    # ---------- Route & Draw ----------
    def clear_path_layer(self):
        for child in self.layer_path.childItems():
            child.setParentItem(None)
            self.scene.removeItem(child)

    def parse_point(self, text: str):
        if not text.strip():
            return None
        s = text.replace('(', '').replace(')', '').replace(' ', '')
        if ',' not in s: return None
        xs, ys = s.split(',', 1)
        try:
            x = float(xs); y = float(ys)
        except ValueError:
            return None
        return self.clamp_point(QPointF(x, y))

    def apply_route_from_inputs(self):
        # 웨이포인트 수집 (최대 3, 최소 1)
        raw_points = [self.parse_point(self.le1.text()),
                      self.parse_point(self.le2.text()),
                      self.parse_point(self.le3.text())]
        waypoints = [p for p in raw_points if p is not None]
        if len(waypoints) < 1:
            QMessageBox.warning(self, "입력 오류", "최소 1개의 웨이포인트를 입력하세요. 예: 1300,925")
            return

        # 각 웨이포인트가 막혀있으면 근처 자유셀로 스냅
        snapped = []
        for p in waypoints:
            snapped.append(self.find_nearest_free_cell_from_point(p))

        # 구간별 A* 이어 붙이기
        segments = []
        prev = self.ENTRANCE
        for goal in snapped:
            c = self.astar(prev, goal)
            if not c:
                QMessageBox.warning(self, "경로 실패", f"경로를 찾을 수 없습니다: {prev} → {goal}")
                return
            segments.append(c)
            prev = goal

        # 셀들을 하나의 경로로 합치고 간소화
        whole = []
        for i, seg in enumerate(segments):
            if i == 0: whole.extend(seg)
            else:      whole.extend(seg[1:])  # 중복 셀 제거
        whole = self.simplify_cells(whole)
        pts = [self.cell_to_pt_center(c) for c in whole]

        # 시작/끝을 실제 좌표로 스냅
        if pts:
            pts[0] = self.ENTRANCE
            pts[-1] = snapped[-1]

        # 그리기
        self.clear_path_layer()
        self.draw_smooth_path(pts)

        # HUD 업데이트
        self.analyze_route_and_update_hud(pts, snapped)

        # 웨이포인트 번호 찍기
        for i, p in enumerate(snapped, start=1):
            t = QGraphicsSimpleTextItem(f"W{i}")
            t.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            t.setPos(p.x()-6, p.y()+10)
            t.setBrush(QColor(30, 30, 30))
            t.setParentItem(self.layer_path)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = ParkingLotUI()
    ui.show()
    sys.exit(app.exec_())