import sys
from heapq import heappush, heappop
from math import sqrt, atan2, degrees
from PyQt5.QtWidgets import (
    QApplication, QGraphicsScene, QGraphicsView, QGraphicsRectItem,
    QGraphicsSimpleTextItem, QGraphicsEllipseItem,
    QPushButton, QWidget, QVBoxLayout, QHBoxLayout, QGraphicsItem,
    QLineEdit, QLabel, QMessageBox, QGraphicsItemGroup, QFrame, QGraphicsObject
)
from PyQt5.QtGui import QBrush, QPainter, QPen, QColor, QPainterPath, QFont, QPolygonF
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal

# ===================================================================
# HUD 위젯: 경로 안내 정보를 표시하는 UI
# ===================================================================
class HudWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumWidth(300)
        self.setStyleSheet("""
            HudWidget { background-color: #1a1a1a; border: 2px solid #444; border-radius: 10px; }
            QLabel { color: #00ff7f; background-color: transparent; }
        """)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setAlignment(Qt.AlignTop)
        title_font = QFont("Arial", 16, QFont.Bold)
        self.title_label = QLabel("경로 안내")
        self.title_label.setFont(title_font)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("color: #ffffff; border-bottom: 1px solid #444; padding-bottom: 10px;")
        self.instruction_list_widget = QWidget()
        self.instruction_layout = QVBoxLayout(self.instruction_list_widget)
        self.instruction_layout.setAlignment(Qt.AlignTop)
        self.layout.addWidget(self.title_label)
        self.layout.addWidget(self.instruction_list_widget)

    def update_instructions(self, instructions):
        while self.instruction_layout.count():
            child = self.instruction_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        if not instructions:
            self.instruction_layout.addWidget(QLabel("경로를 생성하세요."))
            return
        font = QFont("Arial", 12)
        for i, (direction, distance) in enumerate(instructions):
            if i == 0:
                text = f"다음: {direction}\n{distance:.1f}m 앞"
                lbl = QLabel(text)
                lbl.setFont(QFont("Arial", 18, QFont.Bold))
                lbl.setStyleSheet("color: #00ffdd; padding: 10px; border: 1px solid #00ffdd; border-radius: 5px;")
            else:
                text = f"{i+1}. {direction} ({distance:.1f}m)"
                lbl = QLabel(text)
                lbl.setFont(font)
            self.instruction_layout.addWidget(lbl)
        self.instruction_layout.addStretch()

# ===================================================================
# 자동차 아이템: QObject를 상속받아 시그널 사용이 가능하도록 수정
# ===================================================================
class CarItem(QGraphicsObject):
    positionChanged = pyqtSignal(QPointF)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.car_shape = QPolygonF([
            QPointF(-15, -8), QPointF(15, -8), QPointF(15, 8),
            QPointF(10, 12), QPointF(-10, 12), QPointF(-15, 8)
        ])
        self._brush = QBrush(QColor(66, 135, 245))
        self._pen = QPen(Qt.white, 2)
        
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setZValue(100)

    def boundingRect(self):
        return self.car_shape.boundingRect()

    def paint(self, painter, option, widget):
        painter.setBrush(self._brush)
        painter.setPen(self._pen)
        painter.drawPolygon(self.car_shape)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.positionChanged.emit(value)
        return super().itemChange(change, value)

# ===================================================================
# 메인 UI: 주차장 지도 및 컨트롤
# ===================================================================
class ParkingLotUI(QWidget):
    SCENE_W, SCENE_H = 2000, 2000
    CELL, MARGIN, PATH_WIDTH, DRAW_DOTS = 30, 10, 8, False
    PIXELS_PER_METER = 50
    ENTRANCE = QPointF(200, 200)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("실내 주차장 UI (인터랙티브 경로 안내 + HUD)")
        self.setGeometry(50, 50, 1600, 900)

        main_layout = QHBoxLayout(self)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        self.scene = QGraphicsScene(0, 0, self.SCENE_W, self.SCENE_H)
        self.scene.setItemIndexMethod(QGraphicsScene.NoIndex)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setViewportUpdateMode(QGraphicsView.MinimalViewportUpdate)
        self.view.scale(0.5, 0.5); self.view.scale(1, -1); self.view.translate(0, -self.SCENE_H)

        self.le1 = QLineEdit(); self.le1.setPlaceholderText("예: 1300,925 (필수)")
        self.le2 = QLineEdit(); self.le2.setPlaceholderText("예: 1475,925 (선택)")
        self.le3 = QLineEdit(); self.le3.setPlaceholderText("예: 1475,1300 (선택)")
        self.btn_apply = QPushButton("경로 안내")
        self.btn_apply.clicked.connect(self.apply_route_from_inputs)

        row1 = QHBoxLayout(); row1.addWidget(QLabel("W1:")); row1.addWidget(self.le1)
        row2 = QHBoxLayout(); row2.addWidget(QLabel("W2:")); row2.addWidget(self.le2)
        row3 = QHBoxLayout(); row3.addWidget(QLabel("W3:")); row3.addWidget(self.le3)
        controls = QHBoxLayout(); controls.addStretch(1); controls.addWidget(self.btn_apply)

        left_layout.addWidget(self.view)
        left_layout.addLayout(row1); left_layout.addLayout(row2); left_layout.addLayout(row3)
        left_layout.addLayout(controls)

        self.hud = HudWidget()
        main_layout.addWidget(left_panel, 3)
        main_layout.addWidget(self.hud, 1)

        self.layer_static = QGraphicsItemGroup(); self.layer_path = QGraphicsItemGroup()
        self.scene.addItem(self.layer_static); self.scene.addItem(self.layer_path)

        self.full_path_points = []
        self.snapped_waypoints = []
        self.current_path_segment_index = 0
        
        self.car = CarItem()
        self.car.positionChanged.connect(self.update_hud_from_car_position)
        self.scene.addItem(self.car)
        self.car.hide()

        self.build_static_layout()
        self.build_occupancy()
        self.hud.update_instructions([])

    def add_block(self, x, y, w, h, color, label=""):
        r = QGraphicsRectItem(QRectF(x, y, w, h)); r.setBrush(QBrush(color)); r.setPen(QPen(Qt.black)); r.setParentItem(self.layer_static)
        if label: t = QGraphicsSimpleTextItem(label); t.setFlag(QGraphicsItem.ItemIgnoresTransformations, True); t.setPos(x+5, y+h-20); t.setParentItem(self.layer_static)
    def add_hatched(self, x, y, w, h, edge=QColor("black"), fill=QColor(220, 20, 60, 90)):
        r = QGraphicsRectItem(QRectF(x, y, w, h)); b = QBrush(fill); b.setStyle(Qt.BDiagPattern); r.setBrush(b); r.setPen(QPen(edge, 2)); r.setParentItem(self.layer_static)
        t = QGraphicsSimpleTextItem("통행 불가"); t.setFlag(QGraphicsItem.ItemIgnoresTransformations, True); t.setPos(x+10, y+h-25); t.setParentItem(self.layer_static)
    def add_dot_label_static(self, p: QPointF, text: str, color=QColor("blue")):
        d = QGraphicsEllipseItem(p.x()-5, p.y()-5, 10, 10); d.setBrush(QBrush(color)); d.setPen(QPen(Qt.black)); d.setParentItem(self.layer_static)
        t = QGraphicsSimpleTextItem(text); t.setFlag(QGraphicsItem.ItemIgnoresTransformations, True); t.setPos(p.x()-20, p.y()+20); t.setParentItem(self.layer_static)
    def build_static_layout(self):
        c_dis=QColor("#f4a261"); c_ele=QColor("#2a9d8f"); c_gen=QColor("#264653"); c_obs=QColor("#6c757d"); c_emp=QColor("#ced4da"); c_io=QColor("#e76f51")
        border=QGraphicsRectItem(0,0,self.SCENE_W,self.SCENE_H); border.setPen(QPen(QColor("black"),8)); border.setParentItem(self.layer_static)
        base=[(0,1600,300,400,c_dis,"장애인"),(300,1600,300,400,c_dis,"장애인"),(600,1600,200,400,c_gen,"일반"),(800,1600,200,400,c_gen,"일반"),(1000,1600,200,400,c_gen,"일반"),(1200,1600,200,400,c_ele,"전기차"),(1400,1600,200,400,c_ele,"전기차"),(1600,1600,400,400,c_emp,"빈기둥"),(550,1050,800,300,c_obs,"장애물"),(1600,400,400,400,c_emp,"빈기둥"),(0,0,400,400,c_io,"입출차"),]
        for x,y,w,h,c,l in base: self.add_block(x,y,w,h,c,l)
        for i in range(6): self.add_block(400+i*200,400,200,400,c_gen,"일반")
        for i in range(4): self.add_block(1600,800+i*200,400,200,c_gen,"일반")
        self.add_hatched(400,0,1600,400); self.add_dot_label_static(self.ENTRANCE,"입구",QColor("blue"))
    def build_occupancy(self):
        W, H, C = self.SCENE_W, self.SCENE_H, self.CELL; gx, gy = (W + C - 1) // C, (H + C - 1) // C
        self.grid_w, self.grid_h = gx, gy; self.occ = bytearray(gx * gy)
        def idx(cx, cy): return cy * gx + cx
        def block_rect(x, y, w, h):
            x0, y0 = max(0, x - self.MARGIN), max(0, y - self.MARGIN); x1, y1 = min(W, x + w + self.MARGIN), min(H, y + h + self.MARGIN)
            cx0, cy0 = int(x0 // C), int(y0 // C); cx1, cy1 = int((x1 - 1) // C), int((y1 - 1) // C)
            cx0 = max(0, min(cx0, gx - 1)); cx1 = max(0, min(cx1, gx - 1)); cy0 = max(0, min(cy0, gy - 1)); cy1 = max(0, min(cy1, gy - 1))
            for cy in range(cy0, cy1 + 1):
                base = cy * gx
                for cx in range(cx0, cx1 + 1): self.occ[base + cx] = 1
        block_rect(550,1050,800,300); block_rect(400,0,1600,400); block_rect(1600,400,400,400); block_rect(1600,1600,400,400); block_rect(0,1600,300,400); block_rect(300,1600,300,400)
        for i in range(6): block_rect(400 + i*200, 400, 200, 400)
        for i in range(4): block_rect(1600, 800 + i*200, 400, 200)
        block_rect(600,1600,200,400); block_rect(800,1600,200,400); block_rect(1000,1600,200,400); block_rect(1200,1600,200,400); block_rect(1400,1600,200,400)
        self._occ_idx = idx

    def clamp_point(self, p: QPointF): return QPointF(min(self.SCENE_W - 1.0, max(0.0, p.x())), min(self.SCENE_H - 1.0, max(0.0, p.y())))
    def pt_to_cell(self, p: QPointF): cx = int(p.x() // self.CELL); cy = int(p.y() // self.CELL); return max(0, min(cx, self.grid_w - 1)), max(0, min(cy, self.grid_h - 1))
    def cell_to_pt_center(self, c): cx, cy = c; return QPointF(cx * self.CELL + self.CELL / 2.0, cy * self.CELL + self.CELL / 2.0)
    def is_cell_free(self, cx, cy):
        if not (0 <= cx < self.grid_w and 0 <= cy < self.grid_h): return False
        return self.occ[self._occ_idx(cx, cy)] == 0
    def find_nearest_free_cell_from_point(self, p: QPointF, max_radius_cells=30):
        sx, sy = self.pt_to_cell(p)
        if self.is_cell_free(sx, sy): return self.cell_to_pt_center((sx, sy))
        for r in range(1, max_radius_cells + 1):
            for dx in range(-r, r + 1):
                for dy in (-r, r):
                    if self.is_cell_free(sx + dx, sy + dy): return self.cell_to_pt_center((sx + dx, sy + dy))
            for dy in range(-r + 1, r):
                for dx in (-r, r):
                    if self.is_cell_free(sx + dx, sy + dy): return self.cell_to_pt_center((sx + dx, sy + dy))
        return self.cell_to_pt_center((sx, sy))
    def astar(self, start_pt: QPointF, goal_pt: QPointF):
        sx, sy = self.pt_to_cell(start_pt); gx, gy = self.pt_to_cell(goal_pt)
        W, H = self.grid_w, self.grid_h; occ, idx = self.occ, self._occ_idx
        def inb(x, y): return 0 <= x < W and 0 <= y < H
        if not inb(sx, sy) or not inb(gx, gy) or occ[idx(sx, sy)] or occ[idx(gx, gy)]: return None
        nbr = [(1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1)]; heur = lambda x, y: abs(x - gx) + abs(y - gy)
        openh = []; heappush(openh, (heur(sx, sy), 0, (sx, sy))); came = {}; g = {(sx, sy): 0}
        while openh:
            _, gc, (x, y) = heappop(openh)
            if (x, y) == (gx, gy):
                path = []; curr = (x, y)
                while curr in came: path.append(curr); curr = came[curr]
                path.append((sx, sy)); path.reverse(); return path
            for dx, dy, cst in nbr:
                nx, ny = x + dx, y + dy
                if not inb(nx, ny) or occ[idx(nx, ny)]: continue
                ng = gc + cst
                if (nx, ny) not in g or ng < g[(nx, ny)]: g[(nx, ny)] = ng; came[(nx, ny)] = (x, y); heappush(openh, (ng + heur(nx, ny), ng, (nx, ny)))
        return None

    def simplify_cells(self, cells):
        if not cells: return []
        simp = [cells[0]]; norm = lambda vx, vy: ((0 if vx == 0 else (1 if vx > 0 else -1)), (0 if vy == 0 else (1 if vy > 0 else -1)))
        for i in range(1, len(cells) - 1):
            x0, y0 = simp[-1]; x1, y1 = cells[i]; x2, y2 = cells[i+1]
            if norm(x1 - x0, y1 - y0) == norm(x2 - x1, y2 - y1): continue
            simp.append(cells[i])
        if len(cells) > 1 and cells[-1] != simp[-1]: simp.append(cells[-1])
        return simp

    def draw_smooth_path(self, pts):
        if len(pts) < 2: return
        path = QPainterPath(); path.moveTo(pts[0])
        if len(pts) == 2: path.lineTo(pts[1])
        else:
            t = 0.35; m1 = QPointF((pts[0].x() + pts[1].x()) / 2, (pts[0].y() + pts[1].y()) / 2); path.lineTo(m1)
            for i in range(1, len(pts) - 1):
                p0, p1, p2 = pts[i-1], pts[i], pts[i+1]
                m_in = QPointF(p1.x() + (p0.x() - p1.x()) * t, p1.y() + (p0.y() - p1.y()) * t)
                m_out = QPointF(p1.x() + (p2.x() - p1.x()) * t, p1.y() + (p2.y() - p1.y()) * t)
                path.lineTo(m_in); path.quadTo(p1, m_out)
            path.lineTo(pts[-1])
        item = self.scene.addPath(path, QPen(QColor(255, 77, 77, 220), self.PATH_WIDTH, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)); item.setParentItem(self.layer_path)

    def generate_hud_instructions(self, pts):
        if len(pts) < 2: return []
        instructions = []; total_distance = 0
        for i in range(len(pts) - 1):
            p1, p2 = pts[i], pts[i+1]
            dist_meters = sqrt((p2.x() - p1.x())**2 + (p2.y() - p1.y())**2) / self.PIXELS_PER_METER
            total_distance += dist_meters
            if i < len(pts) - 2:
                p3 = pts[i+2]
                angle1 = degrees(atan2(p2.y() - p1.y(), p2.x() - p1.x())); angle2 = degrees(atan2(p3.y() - p2.y(), p3.x() - p2.x()))
                turn_angle = (angle2 - angle1 + 180) % 360 - 180
                direction = ""
                if turn_angle > 45: direction = "좌회전"
                elif turn_angle < -45: direction = "우회전"
                if direction: instructions.append((direction, total_distance)); total_distance = 0
        instructions.append(("목적지 도착", total_distance))
        return instructions

    def clear_path_layer(self):
        for child in self.layer_path.childItems(): child.setParentItem(None); self.scene.removeItem(child)

    def parse_point(self, text: str):
        s = text.strip().replace('(', '').replace(')', '').replace(' ', '');
        if not s or ',' not in s: return None
        try: x, y = map(float, s.split(',', 1)); return self.clamp_point(QPointF(x, y))
        except ValueError: return None

    def apply_route_from_inputs(self):
        waypoints = [p for p in [self.parse_point(le.text()) for le in [self.le1, self.le2, self.le3]] if p]
        if not waypoints:
            QMessageBox.warning(self, "입력 오류", "최소 1개의 웨이포인트를 입력하세요."); return

        self.snapped_waypoints = [self.find_nearest_free_cell_from_point(p) for p in waypoints]
        segments = []; prev = self.ENTRANCE
        for goal in self.snapped_waypoints:
            c = self.astar(prev, goal)
            if not c: QMessageBox.warning(self, "경로 실패", f"{prev} → {goal} 경로를 찾을 수 없습니다."); return
            segments.append(c); prev = goal

        whole = [];
        for i, seg in enumerate(segments): whole.extend(seg if i == 0 else seg[1:])
        
        self.full_path_points = [self.cell_to_pt_center(c) for c in self.simplify_cells(whole)]
        if not self.full_path_points: return

        self.full_path_points[0] = self.ENTRANCE; self.full_path_points[-1] = self.snapped_waypoints[-1]
        
        self.clear_path_layer()
        self.draw_smooth_path(self.full_path_points)
        for i, p in enumerate(self.snapped_waypoints, start=1):
            t = QGraphicsSimpleTextItem(f"W{i}"); t.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            t.setPos(p.x()-6, p.y()+10); t.setBrush(QColor(30,30,30)); t.setParentItem(self.layer_path)

        # 경로 생성 후 상태 초기화
        self.current_path_segment_index = 0
        self.car.setPos(self.ENTRANCE)
        self.car.show()
        self.update_hud_from_car_position(self.ENTRANCE)
        self.btn_apply.setText("경로 재설정")

    def _update_current_segment(self, car_pos):
        """차량의 위치를 기반으로 현재 주행 중인 경로의 구간을 업데이트합니다."""
        if not self.full_path_points or len(self.full_path_points) < 2:
            return

        # 차량이 마지막 구간을 넘어가지 않도록 반복 범위를 제한합니다.
        while self.current_path_segment_index < len(self.full_path_points) - 2:
            p1 = self.full_path_points[self.current_path_segment_index]
            p2 = self.full_path_points[self.current_path_segment_index + 1]

            v = p2 - p1
            if v.x() == 0 and v.y() == 0:
                self.current_path_segment_index += 1
                continue

            w = car_pos - p1
            dot_product = QPointF.dotProduct(w, v)
            length_sq = v.x()**2 + v.y()**2
            t = dot_product / length_sq

            if t > 1:
                # 투영된 위치가 현재 구간의 끝점을 넘었으므로 다음 구간으로 이동합니다.
                self.current_path_segment_index += 1
            else:
                # 차량이 현재 구간 내에 있으므로 루프를 중단합니다.
                break

    def update_hud_from_car_position(self, car_pos):
        """차량의 위치가 변경될 때마다 호출되어 HUD를 업데이트합니다."""
        if not self.full_path_points:
            return

        # 1. 차량의 현재 주행 구간을 갱신합니다.
        self._update_current_segment(car_pos)

        # 2. 현재 위치부터 남은 경로 노드들을 가져옵니다.
        # 다음 턴 지점부터 끝까지의 노드 목록
        remaining_turn_points = self.full_path_points[self.current_path_segment_index + 1:]
        
        # 3. HUD 안내 생성을 위해 경로의 시작점으로 현재 차량 위치를 추가합니다.
        path_for_hud = [car_pos] + remaining_turn_points
        
        if len(path_for_hud) < 2:
            self.hud.update_instructions([("목적지 도착", 0)])
            return
            
        # 4. 생성된 경로를 기반으로 HUD 안내를 업데이트합니다.
        instructions = self.generate_hud_instructions(path_for_hud)
        self.hud.update_instructions(instructions)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = ParkingLotUI()
    ui.show()
    sys.exit(app.exec_())
