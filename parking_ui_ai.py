import sys
from heapq import heappush, heappop
from math import sqrt, atan2, degrees
from PyQt5.QtWidgets import (
    QApplication, QGraphicsScene, QGraphicsView, QGraphicsRectItem,
    QGraphicsSimpleTextItem, QGraphicsEllipseItem,
    QPushButton, QWidget, QVBoxLayout, QHBoxLayout, QGraphicsItem,
    QLineEdit, QLabel, QMessageBox, QGraphicsItemGroup, QFrame, QSplitter
)
from PyQt5.QtGui import QBrush, QPainter, QPen, QColor, QPainterPath, QFont
from PyQt5.QtCore import Qt, QPointF, QRectF

# ========================= HUD 위젯 =========================
class HudWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumWidth(320)
        self.setStyleSheet("""
            HudWidget { background-color: #101012; border: 1px solid #2a2a33; border-radius: 10px; }
            QLabel { color: #dfe6ee; background-color: transparent; }
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16,16,16,16)
        lay.setSpacing(10)

        self.title = QLabel("경로 안내")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("font-size:18px; font-weight:600; padding-bottom:6px; border-bottom:1px solid #2a2a33;")
        self.big = QLabel("경로를 생성하세요.")
        f = QFont(); f.setPointSize(22); f.setBold(True)
        self.big.setFont(f); self.big.setAlignment(Qt.AlignCenter)
        self.sub = QLabel(" "); self.sub.setStyleSheet("color:#8aa0b8")

        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setAlignment(Qt.AlignTop)
        self.list_layout.setSpacing(6)

        lay.addWidget(self.title)
        lay.addWidget(self.big)
        lay.addWidget(self.sub)
        hr = QFrame(); hr.setFrameShape(QFrame.HLine); hr.setFrameShadow(QFrame.Sunken)
        lay.addWidget(hr)
        lay.addWidget(QLabel("전체 단계"))
        lay.addWidget(self.list_container, 1)

    def update_instructions(self, instructions):
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        if not instructions:
            self.big.setText("경로를 생성하세요.")
            self.sub.setText(" ")
            return

        direction, distance = instructions[0]
        self.big.setText(direction)
        self.sub.setText(f"{distance:.1f} m 앞")

        for i, (direction, distance) in enumerate(instructions[1:], start=2):
            lbl = QLabel(f"{i-1}. {direction} ({distance:.1f} m)")
            self.list_layout.addWidget(lbl)
        self.list_layout.addStretch()

# ============ 드래그 가능한 차량 픽토그램 (씬에 직접 추가) ============
class DraggableCar(QGraphicsEllipseItem):
    """
    중심(0,0) 기준 타원. setPos(x,y) 시 (x,y)에 센터가 위치.
    - 이동 가능
    - PositionChange에서 경계 클램프
    - PositionHasChanged에서 on_moved 콜백 호출
    """
    def __init__(self, radius=16, bounds_rect=QRectF(0,0,2000,2000), on_moved=None, parent=None):
        super().__init__(-radius, -radius*0.6, radius*2, radius*1.2, parent)
        self.setBrush(QBrush(QColor("#00d084")))
        self.setPen(QPen(QColor(0,0,0,180), 1.2))
        self.setZValue(2000)
        self.setFlags(
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self._bounds = bounds_rect
        self.on_moved = on_moved

    def hoverEnterEvent(self, e):
        self.setCursor(Qt.OpenHandCursor)
        return super().hoverEnterEvent(e)

    def mousePressEvent(self, e):
        self.setCursor(Qt.ClosedHandCursor)
        return super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        self.setCursor(Qt.OpenHandCursor)
        return super().mouseReleaseEvent(e)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            # 이동 중 경계 클램프
            x = min(self._bounds.right()-1.0, max(self._bounds.left(), value.x()))
            y = min(self._bounds.top()+self._bounds.height()-1.0, max(self._bounds.top(), value.y()))
            return QPointF(x, y)
        elif change == QGraphicsItem.ItemPositionHasChanged:
            if self.on_moved:
                self.on_moved(self.pos())
        return super().itemChange(change, value)

# ========================== 메인 UI ==========================
class ParkingLotUI(QWidget):
    SCENE_W, SCENE_H = 2000, 2000
    CELL, MARGIN, PATH_WIDTH, DRAW_DOTS = 30, 10, 8, False
    PIXELS_PER_METER = 50
    ENTRANCE = QPointF(200, 200)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("실내 주차장 UI (드래그 차량 + HUD)")
        self.setGeometry(40, 40, 1400, 900)

        # 장면/뷰
        self.scene = QGraphicsScene(0, 0, self.SCENE_W, self.SCENE_H)
        self.scene.setItemIndexMethod(QGraphicsScene.NoIndex)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setViewportUpdateMode(QGraphicsView.MinimalViewportUpdate)
        self.view.scale(0.5, 0.5); self.view.scale(1, -1); self.view.translate(0, -self.SCENE_H)

        # HUD
        self.hud = HudWidget()

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.view)
        splitter.addWidget(self.hud)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)

        # 입력
        self.le1 = QLineEdit(); self.le1.setPlaceholderText("예: 1300,925 (필수)")
        self.le2 = QLineEdit(); self.le2.setPlaceholderText("예: 1475,925 (선택)")
        self.le3 = QLineEdit(); self.le3.setPlaceholderText("예: 1475,1300 (선택)")
        self.btn_apply = QPushButton("최적 경로 생성")
        self.btn_apply.clicked.connect(self.apply_route_from_inputs)
        row1 = QHBoxLayout(); row1.addWidget(QLabel("W1:")); row1.addWidget(self.le1)
        row2 = QHBoxLayout(); row2.addWidget(QLabel("W2:")); row2.addWidget(self.le2)
        row3 = QHBoxLayout(); row3.addWidget(QLabel("W3:")); row3.addWidget(self.le3)
        rowb = QHBoxLayout(); rowb.addStretch(1); rowb.addWidget(self.btn_apply)

        root = QVBoxLayout(self)
        root.addWidget(splitter, 1)
        root.addLayout(row1); root.addLayout(row2); root.addLayout(row3)
        root.addLayout(rowb)

        # 레이어
        self.layer_static  = QGraphicsItemGroup(); self.scene.addItem(self.layer_static)
        self.layer_path    = QGraphicsItemGroup(); self.scene.addItem(self.layer_path)
        self.layer_overlay = QGraphicsItemGroup(); self.scene.addItem(self.layer_overlay)
        self.layer_overlay.setHandlesChildEvents(False)  # 그룹이 이벤트 먹지 않도록

        # 상태
        self.full_path_points = []   # 코너 기반 전체 경로
        self.snapped_waypoints = []
        self.base_path_item = None
        self.remain_path_item = None
        self.car = None

        # 초기화
        self.build_static_layout()
        self.build_occupancy()
        self.hud.update_instructions([])

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
        c_dis=QColor("#f4a261"); c_ele=QColor("#2a9d8f"); c_gen=QColor("#264653"); c_obs=QColor("#6c757d")
        c_emp=QColor("#ced4da"); c_io=QColor("#e76f51")
        border=QGraphicsRectItem(0,0,self.SCENE_W,self.SCENE_H); border.setPen(QPen(QColor("black"),8)); border.setParentItem(self.layer_static)
        base=[(0,1600,300,400,c_dis,"장애인"),(300,1600,300,400,c_dis,"장애인"),
              (600,1600,200,400,c_gen,"일반"),(800,1600,200,400,c_gen,"일반"),(1000,1600,200,400,c_gen,"일반"),
              (1200,1600,200,400,c_ele,"전기차"),(1400,1600,200,400,c_ele,"전기차"),
              (1600,1600,400,400,c_emp,"빈기둥"),
              (550,1050,800,300,c_obs,"장애물"),(1600,400,400,400,c_emp,"빈기둥"),
              (0,0,400,400,c_io,"입출차")]
        for x,y,w,h,c,l in base: self.add_block(x,y,w,h,c,l)
        for i in range(6): self.add_block(400+i*200, 400, 200, 400, c_gen, "일반")
        for i in range(4): self.add_block(1600, 800+i*200, 400, 200, c_gen, "일반")
        self.add_hatched(400, 0, 1600, 400)
        self.add_dot_label_static(self.ENTRANCE, "입구", QColor("blue"))

    # ---------- 점유맵 ----------
    def build_occupancy(self):
        W, H, C = self.SCENE_W, self.SCENE_H, self.CELL
        gx, gy = (W + C - 1) // C, (H + C - 1) // C
        self.grid_w, self.grid_h = gx, gy
        self.occ = bytearray(gx * gy)
        def idx(cx, cy): return cy * gx + cx
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
        # 막는 영역
        block_rect(550,1050,800,300)
        block_rect(400,0,1600,400)
        block_rect(1600,400,400,400)
        block_rect(1600,1600,400,400)
        block_rect(0,1600,300,400); block_rect(300,1600,300,400)
        for i in range(6): block_rect(400 + i*200, 400, 200, 400)
        for i in range(4): block_rect(1600, 800 + i*200, 400, 200)
        block_rect(600,1600,200,400); block_rect(800,1600,200,400)
        block_rect(1000,1600,200,400); block_rect(1200,1600,200,400); block_rect(1400,1600,200,400)
        self._occ_idx = idx

    # ---------- 유틸/탐색 ----------
    def clamp_point(self, p: QPointF):
        return QPointF(min(self.SCENE_W-1.0, max(0.0, p.x())),
                       min(self.SCENE_H-1.0, max(0.0, p.y())))
    def pt_to_cell(self, p: QPointF):
        cx = int(p.x() // self.CELL); cy = int(p.y() // self.CELL)
        return max(0, min(cx, self.grid_w-1)), max(0, min(cy, self.grid_h-1))
    def cell_to_pt_center(self, c):
        cx, cy = c
        return QPointF(cx*self.CELL + self.CELL/2.0, cy*self.CELL + self.CELL/2.0)
    def is_cell_free(self, cx, cy):
        if not (0 <= cx < self.grid_w and 0 <= cy < self.grid_h): return False
        return self.occ[self._occ_idx(cx, cy)] == 0
    def find_nearest_free_cell_from_point(self, p: QPointF, max_radius_cells=30):
        sx, sy = self.pt_to_cell(p)
        if self.is_cell_free(sx, sy): return self.cell_to_pt_center((sx, sy))
        for r in range(1, max_radius_cells+1):
            for dx in range(-r, r+1):
                for dy in (-r, r):
                    if self.is_cell_free(sx+dx, sy+dy): return self.cell_to_pt_center((sx+dx, sy+dy))
            for dy in range(-r+1, r):
                for dx in (-r, r):
                    if self.is_cell_free(sx+dx, sy+dy): return self.cell_to_pt_center((sx+dx, sy+dy))
        return self.cell_to_pt_center((sx, sy))

    def astar(self, start_pt: QPointF, goal_pt: QPointF):
        sx, sy = self.pt_to_cell(start_pt); gx, gy = self.pt_to_cell(goal_pt)
        W, H = self.grid_w, self.grid_h; occ, idx = self.occ, self._occ_idx
        def inb(x,y): return 0<=x<W and 0<=y<H
        if not inb(sx,sy) or not inb(gx,gy) or occ[idx(sx,sy)] or occ[idx(gx,gy)]: return None
        nbr = [(1,0,1),(-1,0,1),(0,1,1),(0,-1,1)]
        def heur(x,y): return abs(x-gx)+abs(y-gy)
        openh=[]; heappush(openh,(heur(sx,sy),0,(sx,sy))); came={}; g={(sx,sy):0}
        while openh:
            _, gc, (x,y) = heappop(openh)
            if (x,y)==(gx,gy):
                path=[]; cur=(x,y)
                while cur in came: path.append(cur); cur=came[cur]
                path.append((sx,sy)); path.reverse(); return path
            for dx,dy,cst in nbr:
                nx,ny=x+dx,y+dy
                if not inb(nx,ny) or occ[idx(nx,ny)]: continue
                ng=gc+cst
                if (nx,ny) not in g or ng<g[(nx,ny)]:
                    g[(nx,ny)]=ng; came[(nx,ny)]=(x,y)
                    heappush(openh,(ng+heur(nx,ny),ng,(nx,ny)))
        return None

    # ---------- 경로 후처리/시각화 ----------
    def simplify_cells(self, cells):
        if not cells: return []
        simp=[cells[0]]
        def norm(vx,vy):
            return (0 if vx==0 else (1 if vx>0 else -1),
                    0 if vy==0 else (1 if vy>0 else -1))
        for i in range(1,len(cells)-1):
            x0,y0=simp[-1]; x1,y1=cells[i]; x2,y2=cells[i+1]
            if norm(x1-x0,y1-y0)==norm(x2-x1,y2-y1): continue
            simp.append(cells[i])
        if len(cells)>1 and cells[-1]!=simp[-1]: simp.append(cells[-1])
        return simp

    def draw_poly_smooth(self, pts, color, width, parent_group):
        if len(pts)<2: return None
        path = QPainterPath(); path.moveTo(pts[0])
        if len(pts)==2:
            path.lineTo(pts[1])
        else:
            t=0.35
            m1 = QPointF((pts[0].x()+pts[1].x())/2, (pts[0].y()+pts[1].y())/2)
            path.lineTo(m1)
            for i in range(1,len(pts)-1):
                p0,p1,p2 = pts[i-1], pts[i], pts[i+1]
                m_in  = QPointF(p1.x()+(p0.x()-p1.x())*t, p1.y()+(p0.y()-p1.y())*t)
                m_out = QPointF(p1.x()+(p2.x()-p1.x())*t, p1.y()+(p2.y()-p1.y())*t)
                path.lineTo(m_in); path.quadTo(p1, m_out)
            path.lineTo(pts[-1])
        item = self.scene.addPath(path, QPen(color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        item.setParentItem(parent_group)
        return item

    def clear_group(self, group):
        for ch in list(group.childItems()):
            ch.setParentItem(None)
            self.scene.removeItem(ch)

    # ---------- HUD 문구 ----------
    def generate_hud_instructions(self, pts):
        if len(pts)<2: return []
        out=[]; accum=0.0
        for i in range(len(pts)-1):
            p1,p2=pts[i], pts[i+1]
            accum += sqrt((p2.x()-p1.x())**2 + (p2.y()-p1.y())**2) / self.PIXELS_PER_METER
            if i < len(pts)-2:
                p3 = pts[i+2]
                a1 = degrees(atan2(p2.y()-p1.y(), p2.x()-p1.x()))
                a2 = degrees(atan2(p3.y()-p2.y(), p3.x()-p2.x()))
                turn = (a2-a1+180)%360 - 180
                direction=""
                if turn > 45: direction="좌회전"
                elif turn < -45: direction="우회전"
                if direction:
                    out.append((direction, accum)); accum=0.0
        out.append(("목적지 도착", accum))
        return out

    # ---------- 입력 처리 ----------
    def parse_point(self, text: str):
        s = text.strip().replace('(', '').replace(')', '').replace(' ', '')
        if not s or ',' not in s: return None
        try:
            x,y = map(float, s.split(',',1))
            return self.clamp_point(QPointF(x,y))
        except ValueError:
            return None

    def apply_route_from_inputs(self):
        waypoints = [p for p in [self.parse_point(self.le1.text()),
                                 self.parse_point(self.le2.text()),
                                 self.parse_point(self.le3.text())] if p]
        if not waypoints:
            QMessageBox.warning(self, "입력 오류", "최소 1개의 웨이포인트를 입력하세요.")
            return

        self.snapped_waypoints = [self.find_nearest_free_cell_from_point(p) for p in waypoints]

        # A* 구간 연결
        segments=[]; prev=self.ENTRANCE
        for goal in self.snapped_waypoints:
            cells = self.astar(prev, goal)
            if not cells:
                QMessageBox.warning(self, "경로 실패", f"{prev} → {goal} 경로를 찾을 수 없습니다.")
                return
            segments.append(cells); prev=goal

        whole=[]
        for i,seg in enumerate(segments):
            whole.extend(seg if i==0 else seg[1:])
        self.full_path_points = [self.cell_to_pt_center(c) for c in self.simplify_cells(whole)]
        if not self.full_path_points: return
        self.full_path_points[0] = self.ENTRANCE
        self.full_path_points[-1] = self.snapped_waypoints[-1]

        # 경로 렌더
        self.clear_group(self.layer_path)
        self.clear_group(self.layer_overlay)  # 하이라이트만 비움 (차는 씬에 직접 올림)
        self.base_path_item = self.draw_poly_smooth(self.full_path_points, QColor(255,77,77,130), self.PATH_WIDTH, self.layer_path)

        # 차량 배치 (씬에 직접 추가 → 그룹 이벤트 간섭 없음)
        if self.car is None:
            self.car = DraggableCar(radius=18,
                                    bounds_rect=QRectF(0,0,self.SCENE_W,self.SCENE_H),
                                    on_moved=self.on_car_moved)
            self.scene.addItem(self.car)
        self.car.setPos(self.ENTRANCE)

        # HUD 갱신
        self.update_remaining_from_point(self.car.pos())

    # ---------- 드래그 → HUD/하이라이트 갱신 ----------
    def project_point_to_polyline(self, p: QPointF, poly):
        if len(poly) < 2: return None
        best = (0, poly[0], float('inf'), 0.0)
        px,py = p.x(), p.y()
        for i in range(len(poly)-1):
            a, b = poly[i], poly[i+1]
            ax,ay = a.x(), a.y(); bx,by = b.x(), b.y()
            vx,vy = bx-ax, by-ay
            wx,wy = px-ax, py-ay
            denom = vx*vx + vy*vy
            if denom <= 1e-6:
                t = 0.0; qx,qy = ax, ay
            else:
                t = max(0.0, min(1.0, (wx*vx + wy*vy) / denom))
                qx,qy = ax + t*vx, ay + t*vy
            dx,dy = px-qx, py-qy
            d2 = dx*dx + dy*dy
            if d2 < best[2]:
                best = (i, QPointF(qx,qy), d2, t)
        return best

    def update_remaining_from_point(self, pos: QPointF):
        if not self.full_path_points: return
        proj = self.project_point_to_polyline(pos, self.full_path_points)
        if proj is None: return
        i, q, _, _ = proj
        remaining = [q] + self.full_path_points[i+1:]

        # 하이라이트(차량→도착)
        if self.remain_path_item is not None:
            self.scene.removeItem(self.remain_path_item); self.remain_path_item=None
        self.remain_path_item = self.draw_poly_smooth(remaining, QColor(255,64,64,220), self.PATH_WIDTH+2, self.layer_overlay)

        # HUD 단계
        self.hud.update_instructions(self.generate_hud_instructions(remaining))

    def on_car_moved(self, new_pos: QPointF):
        # itemChange에서 이미 클램프됨 → 여기서는 HUD/하이라이트만 갱신
        self.update_remaining_from_point(new_pos)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = ParkingLotUI()
    ui.show()
    sys.exit(app.exec_())
