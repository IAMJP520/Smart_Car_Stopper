# 입력 필드들
        self.le1 = QLineEdit()
        self.le1.setPlaceholderText("목적지 좌표: 예) 1300,925")
        self.le2 = QLineEdit()
        self.le2.setPlaceholderText("경유지 1: 예) 1475,925 (선택)")
        self.le3 = QLineEdit()
        self.le3.setPlaceholderText("경유지 2: 예) 1475,1300 (선택)")
        
        # 네비게이션 시작 버튼
        self.btn_apply = QPushButton("내비게이션 시작")
        self.btn_apply.clicked.connect(self.apply_route_from_inputs)
        
        controls_layout.addWidget(title_label)
        controls_layout.addWidget(self.le1)
        controls_layout.addWidget(self.le2)
        controls_layout.addWidget(self.le3)
        controls_layout.addWidget(self.btn_apply)

        left_layout.addWidget(self.view, 4)
        left_layout.addWidget(controls_frame, 1)

        # 프리미엄 클러스터 HUD
        self.hud = PremiumClusterHUD()
        
        main_layout.addWidget(left_panel, 3)
        main_layout.addWidget(self.hud, 1)

        # 그래픽 레이어 초기화
        self.layer_static = QGraphicsItemGroup()
        self.layer_path = QGraphicsItemGroup()
        self.scene.addItem(self.layer_static)
        self.scene.addItem(self.layer_path)

        self.full_path_points = []
        self.snapped_waypoints = []
        self.current_path_segment_index = 0
        
        # 프리미엄 자동차
        self.car = PremiumCarItem()
        self.car.positionChanged.connect(self.update_hud_from_car_position)
        self.scene.addItem(self.car)
        self.car.hide()

        self.build_premium_layout()
        self.build_occupancy()
        
        # 초기 HUD 상태
        self.hud.update_navigation_info([])

    def add_premium_block(self, x, y, w, h, block_type, label=""):
        """프리미엄 클러스터 스타일 블록"""
        r = QGraphicsRectItem(QRectF(x, y, w, h))
        
        # 블록 타입별 그라데이션
        if "장애인" in label:
            gradient = QLinearGradient(x, y, x + w, y + h)
            gradient.setColorAt(0, QColor(255, 179, 71, 200))
            gradient.setColorAt(1, QColor(255, 140, 0, 150))
            r.setBrush(QBrush(gradient))
            r.setPen(QPen(QColor(255, 200, 100), 2))
        elif "전기차" in label:
            gradient = QLinearGradient(x, y, x + w, y + h)
            gradient.setColorAt(0, QColor(80, 200, 120, 200))
            gradient.setColorAt(1, QColor(50, 160, 90, 150))
            r.setBrush(QBrush(gradient))
            r.setPen(QPen(QColor(100, 220, 140), 2))
        elif "일반" in label:
            gradient = QLinearGradient(x, y, x + w, y + h)
            gradient.setColorAt(0, QColor(0, 240, 255, 180))
            gradient.setColorAt(1, QColor(77, 166, 255, 130))
            r.setBrush(QBrush(gradient))
            r.setPen(QPen(QColor(120, 200, 255), 2))
        elif "장애물" in label:
            gradient = QLinearGradient(x, y, x + w, y + h)
            gradient.setColorAt(0, QColor(160, 180, 204, 150))
            gradient.setColorAt(1, QColor(108, 117, 125, 120))
            r.setBrush(QBrush(gradient))
            r.setPen(QPen(QColor(180, 190, 200), 2))
        else:
            gradient = QLinearGradient(x, y, x + w, y + h)
            gradient.setColorAt(0, QColor(30, 58, 95, 120))
            gradient.setColorAt(1, QColor(6, 17, 32, 80))
            r.setBrush(QBrush(gradient))
            r.setPen(QPen(QColor(77, 166, 255), 1))
            
        r.setParentItem(self.layer_static)
        
        if label:
            t = QGraphicsSimpleTextItem(label)
            t.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            t.setBrush(QColor(245, 245, 245))
            font = QFont("Segoe UI", 11, QFont.Light)
            t.setFont(font)
            t.setPos(x + 8, y + h - 28)
            t.setParentItem(self.layer_static)

    def add_premium_obstacle(self, x, y, w, h):
        """프리미엄 장애물 표시"""
        r = QGraphicsRectItem(QRectF(x, y, w, h))
        
        # 장애물 패턴
        b = QBrush(QColor(220, 20, 60, 120))
        b.setStyle(Qt.Dense4Pattern)
        r.setBrush(b)
        r.setPen(QPen(QColor(255, 100, 100), 3))
        r.setParentItem(self.layer_static)
        
        t = QGraphicsSimpleTextItem("통행 불가")
        t.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        t.setBrush(QColor(255, 150, 150))
        font = QFont("Segoe UI", 10, QFont.Light)
        t.setFont(font)
        t.setPos(x + 15, y + h - 35)
        t.setParentItem(self.layer_static)

    def add_premium_entrance(self, p: QPointF, text: str):
        """프리미엄 입구 표시"""
        # 메인 원
        d = QGraphicsEllipseItem(p.x() - 12, p.y() - 12, 24, 24)
        entrance_gradient = QRadialGradient(p.x(), p.y(), 12)
        entrance_gradient.setColorAt(0, QColor(0, 240, 255, 220))
        entrance_gradient.setColorAt(0.7, QColor(77, 166, 255, 180))
        entrance_gradient.setColorAt(1, QColor(0, 240, 255, 0))
        d.setBrush(QBrush(entrance_gradient))
        d.setPen(QPen(QColor(245, 245, 245), 3))
        d.setParentItem(self.layer_static)
        
        # 글로우 링
        glow_ring = QGraphicsEllipseItem(p.x() - 18, p.y() - 18, 36, 36)
        glow_ring.setBrush(QBrush(QColor(0, 0, 0, 0)))
        glow_ring.setPen(QPen(QColor(0, 240, 255, 100), 2))
        glow_ring.setParentItem(self.layer_static)
        
        t = QGraphicsSimpleTextItem(text)
        t.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        t.setBrush(QColor(0, 240, 255))
        font = QFont("Segoe UI", 13, QFont.Light)
        t.setFont(font)
        t.setPos(p.x() - 25, p.y() + 30)
        t.setParentItem(self.layer_static)

    def build_premium_layout(self):
        """프리미엄 레이아웃 구성"""
        # 외곽 테두리
        border = QGraphicsRectItem(0, 0, self.SCENE_W, self.SCENE_H)
        border.setPen(QPen(QColor(0, 240, 255), 8))
        border.setBrush(QBrush(QColor(0, 0, 0, 0)))
        border.setParentItem(self.layer_static)
        
        # 주차 구역 배치
        parking_zones = [
            (0, 1600, 300, 400, "장애인"),
            (300, 1600, 300, 400, "장애인"),
            (600, 1600, 200, 400, "일반"),
            (800, 1600, 200, 400, "일반"),
            (1000, 1600, 200, 400, "일반"),
            (1200, 1600, 200, 400, "전기차"),
            (1400, 1600, 200, 400, "전기차"),
            (1600, 1600, 400, 400, "빈공간"),
            (550, 1050, 800, 300, "장애물"),
            (1600, 400, 400, 400, "빈공간"),
            (0, 0, 400, 400, "입출차"),
        ]
        
        for x, y, w, h, zone_type in parking_zones:
            if zone_type == "장애물":
                self.add_premium_obstacle(x, y, w, h)
            else:
                self.add_premium_block(x, y, w, h, zone_type, zone_type)
        
        # 일반 주차구역 추가
        for i in range(6):
            self.add_premium_block(400 + i * 200, 400, 200, 400, "일반", "일반")
        
        for i in range(4):
            self.add_premium_block(1600, 800 + i * 200, 400, 200, "일반", "일반")
        
        # 통행 불가 구역
        self.add_premium_obstacle(400, 0, 1600, 400)
        
        # 입구 표시
        self.add_premium_entrance(self.ENTRANCE, "ENTRANCE")

    def build_occupancy(self):
        """점유 그리드 생성"""
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
            cx0 = max(0, min(cx0, gx - 1))
            cx1 = max(0, min(cx1, gx - 1))
            cy0 = max(0, min(cy0, gy - 1))
            cy1 = max(0, min(cy1, gy - 1))
            for cy in range(cy0, cy1 + 1):
                base = cy * gx
                for cx in range(cx0, cx1 + 1):
                    self.occ[base + cx] = 1
        
        # 장애물 및 주차구역 블록화
        obstacle_areas = [
            (550, 1050, 800, 300), (400, 0, 1600, 400), 
            (1600, 400, 400, 400), (1600, 1600, 400, 400),
            (0, 1600, 300, 400), (300, 1600, 300, 400),
            (600, 1600, 200, 400), (800, 1600, 200, 400),
            (1000, 1600, 200, 400), (1200, 1600, 200, 400),
            (1400, 1600, 200, 400)
        ]
        
        for x, y, w, h in obstacle_areas:
            block_rect(x, y, w, h)
        
        for i in range(6):
            block_rect(400 + i * 200, 400, 200, 400)
        for i in range(4):
            block_rect(1600, 800 + i * 200, 400, 200)
        
        self._occ_idx = idx

    def clamp_point(self, p: QPointF):
        return QPointF(min(self.SCENE_W - 1.0, max(0.0, p.x())), 
                      min(self.SCENE_H - 1.0, max(0.0, p.y())))
    
    def pt_to_cell(self, p: QPointF):
        cx = int(p.x() // self.CELL)
        cy = int(p.y() // self.CELL)
        return max(0, min(cx, self.grid_w - 1)), max(0, min(cy, self.grid_h - 1))
    
    def cell_to_pt_center(self, c):
        cx, cy = c
        return QPointF(cx * self.CELL + self.CELL / 2.0, cy * self.CELL + self.CELL / 2.0)
    
    def is_cell_free(self, cx, cy):
        if not (0 <= cx < self.grid_w and 0 <= cy < self.grid_h):
            return False
        return self.occ[self._occ_idx(cx, cy)] == 0
    
    def find_nearest_free_cell_from_point(self, p: QPointF, max_radius_cells=30):
        sx, sy = self.pt_to_cell(p)
        if self.is_cell_free(sx, sy):
            return self.cell_to_pt_center((sx, sy))
        
        for r in range(1, max_radius_cells + 1):
            for dx in range(-r, r + 1):
                for dy in (-r, r):
                    if self.is_cell_free(sx + dx, sy + dy):
                        return self.cell_to_pt_center((sx + dx, sy + dy))
            for dy in range(-r + 1, r):
                for dx in (-r, r):
                    if self.is_cell_free(sx + dx, sy + dy):
                        return self.cell_to_pt_center((sx + dx, sy + dy))
        return self.cell_to_pt_center((sx, sy))

    def astar(self, start_pt: QPointF, goal_pt: QPointF):
        """A* 경로 탐색"""
        sx, sy = self.pt_to_cell(start_pt)
        gx, gy = self.pt_to_cell(goal_pt)
        W, H = self.grid_w, self.grid_h
        occ, idx = self.occ, self._occ_idx
        
        def inb(x, y): return 0 <= x < W and 0 <= y < H
        
        if not inb(sx, sy) or not inb(gx, gy) or occ[idx(sx, sy)] or occ[idx(gx, gy)]:
            return None
        
        nbr = [(1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1)]
        heur = lambda x, y: abs(x - gx) + abs(y - gy)
        
        openh = []
        heappush(openh, (heur(sx, sy), 0, (sx, sy)))
        came = {}
        g = {(sx, sy): 0}
        
        while openh:
            _, gc, (x, y) = heappop(openh)
            if (x, y) == (gx, gy):
                path = []
                curr = (x, y)
                while curr in came:
                    path.append(curr)
                    curr = came[curr]
                path.append((sx, sy))
                path.reverse()
                return path
            
            for dx, dy, cst in nbr:
                nx, ny = x + dx, y + dy
                if not inb(nx, ny) or occ[idx(nx, ny)]:
                    continue
                ng = gc + cst
                if (nx, ny) not in g or ng < g[(nx, ny)]:
                    g[(nx, ny)] = ng
                    came[(nx, ny)] = (x, y)
                    heappush(openh, (ng + heur(nx, ny), ng, (nx, ny)))
        
        return None

    def simplify_cells(self, cells):
        """경로 단순화"""
        if not cells:
            return []
        simp = [cells[0]]
        norm = lambda vx, vy: ((0 if vx == 0 else (1 if vx > 0 else -1)), 
                              (0 if vy == 0 else (1 if vy > 0 else -1)))
        
        for i in range(1, len(cells) - 1):
            x0, y0 = simp[-1]
            x1, y1 = cells[i]
            x2, y2 = cells[i + 1]
            if norm(x1 - x0, y1 - y0) == norm(x2 - x1, y2 - y1):
                continue
            simp.append(cells[i])
        
        if len(cells) > 1 and cells[-1] != simp[-1]:
            simp.append(cells[-1])
        return simp

    def draw_premium_path(self, pts):
        """프리미엄 경로 그리기"""
        if len(pts) < 2:
            return
        
        path = QPainterPath()
        path.moveTo(pts[0])
        
        if len(pts) == 2:
            path.lineTo(pts[1])
        else:
            t = 0.4
            m1 = QPointF((pts[0].x() + pts[1].x()) / 2, (pts[0].y() + pts[1].y()) / 2)
            path.lineTo(m1)
            
            for i in range(1, len(pts) - 1):
                p0, p1, p2 = pts[i - 1], pts[i], pts[i + 1]
                m_in = QPointF(p1.x() + (p0.x() - p1.x()) * t, p1.y() + (p0.y() - p1.y()) * t)
                m_out = QPointF(p1.x() + (p2.x() - p1.x()) * t, p1.y() + (p2.y() - p1.y()) * t)
                path.lineTo(m_in)
                path.quadTo(p1, m_out)
            
            path.lineTo(pts[-1])
        
        # 글로우 효과 (외곽)
        glow_pen = QPen(QColor(0, 240, 255, 80), self.PATH_WIDTH + 8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        item_glow = self.scene.addPath(path, glow_pen)
        item_glow.setParentItem(self.layer_path)
        
        # 메인 경로
        main_pen = QPen(QColor(0, 240, 255, 220), self.PATH_WIDTH, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        item_main = self.scene.addPath(path, main_pen)
        item_main.setParentItem(self.layer_path)
        
        # 중앙 하이라이트
        highlight_pen = QPen(QColor(245, 245, 245, 150), self.PATH_WIDTH - 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        item_highlight = self.scene.addPath(path, highlight_pen)
        item_highlight.setParentItem(self.layer_path)

    def generate_hud_instructions(self, pts):
        """HUD 안내 생성"""
        if len(pts) < 2:
            return []
        
        instructions = []
        total_distance = 0
        
        for i in range(len(pts) - 1):
            p1, p2 = pts[i], pts[i + 1]
            dist_meters = sqrt((p2.x() - p1.x()) ** 2 + (p2.y() - p1.y()) ** 2) / self.PIXELS_PER_METER
            total_distance += dist_meters
            
            if i < len(pts) - 2:
                p3 = pts[i + 2]
                angle1 = degrees(atan2(p2.y() - p1.y(), p2.x() - p1.x()))
                angle2 = degrees(atan2(p3.y() - p2.y(), p3.x() - p2.x()))
                turn_angle = (angle2 - angle1 + 180) % 360 - 180
                
                direction = ""
                if turn_angle > 45:
                    direction = "좌회전"
                elif turn_angle < -45:
                    direction = "우회전"
                
                if direction:
                    instructions.append((direction, total_distance))
                    total_distance = 0
        
        instructions.append(("목적지 도착", total_distance))
        return instructions

    def calculate_route_progress(self, car_pos):
        """경로 진행률 계산"""
        if not self.full_path_points or len(self.full_path_points) < 2:
            return 0
        
        total_length = 0
        for i in range(len(self.full_path_points) - 1):
            p1, p2 = self.full_path_points[i], self.full_path_points[i + 1]
            total_length += sqrt((p2.x() - p1.x()) ** 2 + (p2.y() - p1.y()) ** 2)
        
        if total_length == 0:
            return 0
        
        min_dist = float('inf')
        closest_segment = 0
        projection_ratio = 0
        
        for i in range(len(self.full_path_points) - 1):
            p1 = self.full_path_points[i]
            p2 = self.full_path_points[i + 1]
            
            segment_vec = QPointF(p2.x() - p1.x(), p2.y() - p1.y())
            car_vec = QPointF(car_pos.x() - p1.x(), car_pos.y() - p1.y())
            
            segment_length_sq = segment_vec.x() ** 2 + segment_vec.y() ** 2
            
            if segment_length_sq == 0:
                continue
            
            t = max(0, min(1, (car_vec.x() * segment_vec.x() + car_vec.y() * segment_vec.y()) / segment_length_sq))
            projection = QPointF(p1.x() + t * segment_vec.x(), p1.y() + t * segment_vec.y())
            dist = sqrt((car_pos.x() - projection.x()) ** 2 + (car_pos.y() - projection.y()) ** 2)
            
            if dist < min_dist:
                min_dist = dist
                closest_segment = i
                projection_ratio = t
        
        traveled_length = 0
        for i in range(closest_segment):
            p1, p2 = self.full_path_points[i], self.full_path_points[i + 1]
            traveled_length += sqrt((p2.x() - p1.x()) ** 2 + (p2.y() - p1.y()) ** 2)
        
        if closest_segment < len(self.full_path_points) - 1:
            p1, p2 = self.full_path_points[closest_segment], self.full_path_points[closest_segment + 1]
            segment_length = sqrt((p2.x() - p1.x()) ** 2 + (p2.y() - p1.y()) ** 2)
            traveled_length += segment_length * projection_ratio
        
        progress = min(100, (traveled_length / total_length) * 100)
        return progress

    def clear_path_layer(self):
        """경로 레이어 클리어"""
        for child in self.layer_path.childItems():
            child.setParentItem(None)
            self.scene.removeItem(child)

    def parse_point(self, text: str):
        """좌표 파싱"""
        s = text.strip().replace('(', '').replace(')', '').replace(' ', '')
        if not s or ',' not in s:
            return None
        try:
            x, y = map(float, s.split(',', 1))
            return self.clamp_point(QPointF(x, y))
        except ValueError:
            return None

    def apply_route_from_inputs(self):
        """경로 적용"""
        waypoints = [p for p in [self.parse_point(le.text()) for le in [self.le1, self.le2, self.le3]] if p]
        if not waypoints:
            QMessageBox.warning(self, "입력 오류", "최소 1개의 목적지를 입력하세요.")
            return

        self.snapped_waypoints = [self.find_nearest_free_cell_from_point(p) for p in waypoints]
        segments = []
        prev = self.ENTRANCE
        
        for goal in self.snapped_waypoints:
            c = self.astar(prev, goal)
            if not c:
                QMessageBox.warning(self, "경로 실패", f"경로를 찾을 수 없습니다.")
                return
            segments.append(c)
            prev = goal

        whole = []
        for i, seg in enumerate(segments):
            whole.extend(seg if i == 0 else seg[1:])
        
        self.full_path_points = [self.cell_to_pt_center(c) for c in self.simplify_cells(whole)]
        if not self.full_path_points:
            return

        self.full_path_points[0] = self.ENTRANCE
        self.full_path_points[-1] = self.snapped_waypoints[-1]
        
        self.clear_path_layer()
        self.draw_premium_path(self.full_path_points)
        
        # 웨이포인트 표시
        for i, p in enumerate(self.snapped_waypoints, start=1):
            # 웨이포인트 원
            waypoint_circle = QGraphicsEllipseItem(p.x() - 15, p.y() - 15, 30, 30)
            waypoint_gradient = QRadialGradient(p.x(), p.y(), 15)
            waypoint_gradient.setColorAt(0, QColor(255, 179, 71, 220))
            waypoint_gradient.setColorAt(0.7, QColor(255, 140, 0, 180))
            waypoint_gradient.setColorAt(1, QColor(255, 179, 71, 0))
            waypoint_circle.setBrush(QBrush(waypoint_gradient))
            waypoint_circle.setPen(QPen(QColor(245, 245, 245), 3))
            waypoint_circle.setParentItem(self.layer_path)
            
            # 웨이포인트 텍스트
            t = QGraphicsSimpleTextItem(f"W{i}")
            t.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            t.setBrush(QColor(245, 245, 245))
            font = QFont("Segoe UI", 12, QFont.Light)
            t.setFont(font)
            t.setPos(p.x() - 8, p.y() - 6)
            t.setParentItem(self.layer_path)

        # 경로 생성 후 상태 초기화
        self.current_path_segment_index = 0
        self.car.setPos(self.ENTRANCE)
        self.car.show()
        self.update_hud_from_car_position(self.ENTRANCE)
        self.btn_apply.setText("경로 재설정")

    def _update_current_segment(self, car_pos):
        """현재 구간 업데이트"""
        if not self.full_path_points or len(self.full_path_points) < 2:
            return

        while self.current_path_segment_index < len(self.full_path_points) - 2:
            p1 = self.full_path_points[self.current_path_segment_index]
            p2 = self.full_path_points[self.current_path_segment_index + 1]

            v = p2 - p1
            if v.x() == 0 and v.y() == 0:
                self.current_path_segment_index += 1
                continue

            w = car_pos - p1
            dot_product = QPointF.dotProduct(w, v)
            length_sq = v.x() ** 2 + v.y() ** 2
            t = dot_product / length_sq

            if t > 1:
                self.current_path_segment_index += 1
            else:
                break

    def update_hud_from_car_position(self, car_pos):
        """차량 위치 기반 HUD 업데이트"""
        if not self.full_path_points:
            return

        self._update_current_segment(car_pos)
        remaining_turn_points = self.full_path_points[self.current_path_segment_index + 1:]
        
        path_for_hud = [car_pos] + remaining_turn_points
        
        if len(path_for_hud) < 2:
            # 목적지 도착
            self.hud.update_navigation_info([("목적지 도착", 0)], 
                                           current_speed=0, 
                                           route_progress=100)
            return
            
        instructions = self.generate_hud_instructions(path_for_hud)
        progress = self.calculate_route_progress(car_pos)
        
        # 클러스터 스타일 속도 계산 (진행률 기반)
        speed = min(80, int(progress * 0.8 + 15))  # 15~95 km/h 범위
        
        self.hud.update_navigation_info(instructions, 
                                       current_speed=speed, 
                                       route_progress=progress)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 프리미엄 클러스터 스타일 설정
    app.setStyle('Fusion')
    
    # 고급 폰트 설정
    font = QFont("Segoe UI", 12, QFont.Light)
    app.setFont(font)
    
    # 클러스터 다크 팔레트
    app.setStyleSheet(f"""
        QApplication {{
            background-color: {HYUNDAI_CLUSTER_COLORS['background_primary']};
        }}
        QMessageBox {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {HYUNDAI_CLUSTER_COLORS['background_secondary']},
                stop:1 {HYUNDAI_CLUSTER_COLORS['background_primary']});
            color: {HYUNDAI_CLUSTER_COLORS['text_primary']};
            border: 2px solid {HYUNDAI_CLUSTER_COLORS['neon_cyan']};
            border-radius: 20px;
            font-family: 'Segoe UI';
            font-weight: 300;
        }}
        QMessageBox QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {HYUNDAI_CLUSTER_COLORS['accent_blue']}, 
                stop:1 {HYUNDAI_CLUSTER_COLORS['glow_blue']});
            border: 2px solid {HYUNDAI_CLUSTER_COLORS['neon_cyan']};
            border-radius: 10px;
            color: {HYUNDAI_CLUSTER_COLORS['warm_white']};
            font-weight: 300;
            padding: 10px 20px;
            min-width: 80px;
        }}
        QMessageBox QPushButton:hover {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {HYUNDAI_CLUSTER_COLORS['neon_cyan']}, 
                stop:1 {HYUNDAI_CLUSTER_COLORS['glow_blue']});
        }}
    """)
    
    ui = PremiumParkingUI()
    ui.show()
    sys.exit(app.exec_())import sys
from heapq import heappush, heappop
from math import sqrt, atan2, degrees
from PyQt5.QtWidgets import (
    QApplication, QGraphicsScene, QGraphicsView, QGraphicsRectItem,
    QGraphicsSimpleTextItem, QGraphicsEllipseItem,
    QPushButton, QWidget, QVBoxLayout, QHBoxLayout, QGraphicsItem,
    QLineEdit, QLabel, QMessageBox, QGraphicsItemGroup, QFrame, QGraphicsObject
)
from PyQt5.QtGui import QBrush, QPainter, QPen, QColor, QPainterPath, QFont, QPolygonF, QLinearGradient, QRadialGradient
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty

# ===================================================================
# 현대차 프리미엄 클러스터 컬러 팔레트
# ===================================================================
HYUNDAI_CLUSTER_COLORS = {
    'background_primary': '#0A1A2F',     # 다크 네이비 블루
    'background_secondary': '#142B47',   # 미드나잇 블루  
    'neon_cyan': '#00F0FF',             # 네온 사이언
    'warm_white': '#F5F5F5',            # 웜 화이트
    'accent_blue': '#1E3A5F',           # 딥 블루
    'glow_blue': '#4DA6FF',             # 글로우 블루
    'shadow_dark': '#061120',           # 섀도우 다크
    'text_primary': '#F5F5F5',          # 메인 텍스트
    'text_secondary': '#A0B4CC',        # 서브 텍스트
    'warning_amber': '#FFB347',         # 경고색
    'success_green': '#50C878'          # 성공색
}

# ===================================================================
# 프리미엄 클러스터 HUD 위젯
# ===================================================================
class PremiumClusterHUD(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self.setMinimumSize(450, 650)
        self.setStyleSheet(f"""
            PremiumClusterHUD {{ 
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {HYUNDAI_CLUSTER_COLORS['background_primary']}, 
                    stop:0.7 {HYUNDAI_CLUSTER_COLORS['background_secondary']}, 
                    stop:1 {HYUNDAI_CLUSTER_COLORS['shadow_dark']});
                border: 2px solid {HYUNDAI_CLUSTER_COLORS['glow_blue']};
                border-radius: 25px;
            }}
        """)
        
        # 네비게이션 정보
        self.current_direction = "직진"
        self.current_distance = 0.0
        self.next_direction = ""
        self.speed = 0
        self.progress = 0
        
        # 애니메이션 타이머
        self.glow_animation_timer = QTimer()
        self.glow_animation_timer.timeout.connect(self.update_glow)
        self.glow_animation_timer.start(50)
        self.glow_phase = 0
        
    def update_glow(self):
        """글로우 효과 애니메이션"""
        self.glow_phase = (self.glow_phase + 1) % 120
        self.update()
        
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect()
        center_x = rect.width() // 2
        
        # === 배경 엣지 라이트 효과 ===
        self.draw_edge_lighting(painter, rect)
        
        # === 1. 상단: 속도 표시기 ===
        self.draw_speed_gauge(painter, center_x, 120)
        
        # === 2. 중앙: 메인 방향 표시 ===
        self.draw_main_direction(painter, center_x, 280)
        
        # === 3. 거리 정보 ===
        self.draw_distance_display(painter, center_x, 380)
        
        # === 4. 진행률 바 ===
        self.draw_progress_bar(painter, center_x, 480)
        
        # === 5. 하단: 다음 안내 ===
        self.draw_next_guidance(painter, center_x, 560)

    def draw_edge_lighting(self, painter, rect):
        """현대차 클러스터 엣지 라이트 효과"""
        painter.save()
        
        # 외곽 글로우 효과
        glow_intensity = 50 + 30 * abs(1 - (self.glow_phase % 60) / 30.0)
        
        # 상단 엣지 라이트
        top_gradient = QLinearGradient(0, 0, rect.width(), 0)
        top_gradient.setColorAt(0, QColor(0, 240, 255, 0))
        top_gradient.setColorAt(0.3, QColor(0, 240, 255, int(glow_intensity)))
        top_gradient.setColorAt(0.7, QColor(0, 240, 255, int(glow_intensity)))
        top_gradient.setColorAt(1, QColor(0, 240, 255, 0))
        
        painter.setBrush(QBrush(top_gradient))
        painter.setPen(Qt.NoPen)
        painter.drawRect(20, 20, rect.width() - 40, 4)
        
        # 하단 엣지 라이트
        painter.drawRect(20, rect.height() - 24, rect.width() - 40, 4)
        
        # 좌우 세로 라이트
        left_gradient = QLinearGradient(0, 0, 0, rect.height())
        left_gradient.setColorAt(0, QColor(0, 240, 255, 0))
        left_gradient.setColorAt(0.5, QColor(0, 240, 255, int(glow_intensity * 0.7)))
        left_gradient.setColorAt(1, QColor(0, 240, 255, 0))
        
        painter.setBrush(QBrush(left_gradient))
        painter.drawRect(20, 20, 4, rect.height() - 40)
        painter.drawRect(rect.width() - 24, 20, 4, rect.height() - 40)
        
        painter.restore()

    def draw_speed_gauge(self, painter, center_x, y):
        """프리미엄 속도 게이지"""
        painter.save()
        
        # 배경 패널
        panel_rect = QRectF(center_x - 100, y - 50, 200, 100)
        
        # 패널 그라데이션
        panel_gradient = QLinearGradient(panel_rect.topLeft(), panel_rect.bottomRight())
        panel_gradient.setColorAt(0, QColor(30, 58, 95, 180))
        panel_gradient.setColorAt(1, QColor(6, 17, 32, 120))
        
        painter.setBrush(QBrush(panel_gradient))
        painter.setPen(QPen(QColor(0, 240, 255, 100), 2))
        painter.drawRoundedRect(panel_rect, 20, 20)
        
        # 내부 글로우
        inner_glow = QRadialGradient(center_x, y, 80)
        inner_glow.setColorAt(0, QColor(0, 240, 255, 30))
        inner_glow.setColorAt(1, QColor(0, 240, 255, 0))
        painter.setBrush(QBrush(inner_glow))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center_x - 80, y - 40, 160, 80)
        
        # 속도 텍스트
        painter.setFont(QFont("Segoe UI", 36, QFont.Light))
        painter.setPen(QPen(QColor(245, 245, 245)))
        
        speed_text = f"{self.speed}"
        fm = painter.fontMetrics()
        text_width = fm.width(speed_text)
        painter.drawText(center_x - text_width//2, y + 12, speed_text)
        
        # km/h 라벨
        painter.setFont(QFont("Segoe UI", 12, QFont.Light))
        painter.setPen(QPen(QColor(160, 180, 204)))
        painter.drawText(center_x - 15, y + 35, "km/h")
        
        painter.restore()

    def draw_main_direction(self, painter, center_x, y):
        """메인 방향 표시 - 클러스터 스타일"""
        painter.save()
        
        # 중앙 원형 패널
        circle_radius = 70
        
        # 원형 배경 그라데이션
        circle_gradient = QRadialGradient(center_x, y, circle_radius)
        
        if self.current_distance <= 5 and ("좌회전" in self.current_direction or "우회전" in self.current_direction or "목적지" in self.current_direction):
            # 긴급 상황 - 앰버 글로우
            circle_gradient.setColorAt(0, QColor(255, 179, 71, 200))
            circle_gradient.setColorAt(0.7, QColor(255, 179, 71, 100))
            circle_gradient.setColorAt(1, QColor(255, 179, 71, 0))
        else:
            # 일반 상황 - 네온 사이언 글로우
            circle_gradient.setColorAt(0, QColor(0, 240, 255, 150))
            circle_gradient.setColorAt(0.7, QColor(0, 240, 255, 80))
            circle_gradient.setColorAt(1, QColor(0, 240, 255, 0))
        
        painter.setBrush(QBrush(circle_gradient))
        painter.setPen(QPen(QColor(0, 240, 255, 150), 3))
        painter.drawEllipse(center_x - circle_radius, y - circle_radius, 
                          circle_radius * 2, circle_radius * 2)
        
        # 방향 아이콘
        painter.setPen(QPen(QColor(245, 245, 245), 8))
        painter.setBrush(QBrush(QColor(245, 245, 245)))
        
        if self.current_distance <= 5:
            if "좌회전" in self.current_direction:
                self.draw_cluster_left_arrow(painter, center_x, y)
            elif "우회전" in self.current_direction:
                self.draw_cluster_right_arrow(painter, center_x, y)
            elif "목적지" in self.current_direction:
                self.draw_cluster_destination(painter, center_x, y)
            else:
                self.draw_cluster_straight_arrow(painter, center_x, y)
        else:
            self.draw_cluster_straight_arrow(painter, center_x, y)
        
        painter.restore()

    def draw_cluster_straight_arrow(self, painter, x, y):
        """클러스터 스타일 직진 화살표"""
        arrow = QPolygonF([
            QPointF(x, y - 40),
            QPointF(x - 20, y - 15),
            QPointF(x - 10, y - 15),
            QPointF(x - 10, y + 30),
            QPointF(x + 10, y + 30),
            QPointF(x + 10, y - 15),
            QPointF(x + 20, y - 15)
        ])
        painter.drawPolygon(arrow)

    def draw_cluster_left_arrow(self, painter, x, y):
        """클러스터 스타일 좌회전 화살표"""
        arrow = QPolygonF([
            QPointF(x - 40, y),
            QPointF(x - 15, y - 20),
            QPointF(x - 15, y - 10),
            QPointF(x + 30, y - 10),
            QPointF(x + 30, y + 10),
            QPointF(x - 15, y + 10),
            QPointF(x - 15, y + 20)
        ])
        painter.drawPolygon(arrow)

    def draw_cluster_right_arrow(self, painter, x, y):
        """클러스터 스타일 우회전 화살표"""
        arrow = QPolygonF([
            QPointF(x + 40, y),
            QPointF(x + 15, y - 20),
            QPointF(x + 15, y - 10),
            QPointF(x - 30, y - 10),
            QPointF(x - 30, y + 10),
            QPointF(x + 15, y + 10),
            QPointF(x + 15, y + 20)
        ])
        painter.drawPolygon(arrow)

    def draw_cluster_destination(self, painter, x, y):
        """클러스터 스타일 목적지 표시"""
        # 체크 마크
        painter.setPen(QPen(QColor(245, 245, 245), 10))
        painter.drawLine(x - 25, y, x - 10, y + 15)
        painter.drawLine(x - 10, y + 15, x + 25, y - 20)

    def draw_distance_display(self, painter, center_x, y):
        """거리 정보 디스플레이"""
        painter.save()
        
        # 거리 텍스트
        distance_text = f"{self.current_distance:.0f}m"
        if self.current_distance >= 1000:
            distance_text = f"{self.current_distance/1000:.1f}km"
        
        # 메인 거리 텍스트
        painter.setFont(QFont("Segoe UI", 48, QFont.Light))
        
        # 거리에 따른 색상
        if self.current_distance <= 5:
            painter.setPen(QPen(QColor(255, 179, 71)))  # 앰버
        elif self.current_distance <= 20:
            painter.setPen(QPen(QColor(80, 200, 120)))  # 그린
        else:
            painter.setPen(QPen(QColor(0, 240, 255)))   # 네온 사이언
        
        fm = painter.fontMetrics()
        text_width = fm.width(distance_text)
        painter.drawText(center_x - text_width//2, y, distance_text)
        
        # 방향 설명
        painter.setFont(QFont("Segoe UI", 14, QFont.Light))
        painter.setPen(QPen(QColor(160, 180, 204)))
        
        direction_text = self.current_direction
        if len(direction_text) > 15:
            direction_text = direction_text[:15] + "..."
        
        fm2 = painter.fontMetrics()
        text_width2 = fm2.width(direction_text)
        painter.drawText(center_x - text_width2//2, y + 25, direction_text)
        
        painter.restore()

    def draw_progress_bar(self, painter, center_x, y):
        """프리미엄 진행률 바"""
        painter.save()
        
        bar_width = 300
        bar_height = 8
        bar_x = center_x - bar_width // 2
        
        # 배경 바
        bg_rect = QRectF(bar_x, y, bar_width, bar_height)
        painter.setBrush(QBrush(QColor(30, 58, 95, 100)))
        painter.setPen(QPen(QColor(0, 240, 255, 50), 1))
        painter.drawRoundedRect(bg_rect, 4, 4)
        
        # 진행률 바
        progress_width = (bar_width * self.progress) / 100
        if progress_width > 0:
            progress_rect = QRectF(bar_x, y, progress_width, bar_height)
            
            # 진행률 그라데이션
            progress_gradient = QLinearGradient(bar_x, y, bar_x + progress_width, y)
            progress_gradient.setColorAt(0, QColor(0, 240, 255, 200))
            progress_gradient.setColorAt(1, QColor(77, 166, 255, 200))
            
            painter.setBrush(QBrush(progress_gradient))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(progress_rect, 4, 4)
        
        # 진행률 텍스트
        painter.setFont(QFont("Segoe UI", 12, QFont.Light))
        painter.setPen(QPen(QColor(245, 245, 245)))
        progress_text = f"{self.progress:.0f}%"
        fm = painter.fontMetrics()
        text_width = fm.width(progress_text)
        painter.drawText(center_x - text_width//2, y + 25, progress_text)
        
        painter.restore()

    def draw_next_guidance(self, painter, center_x, y):
        """다음 안내 표시"""
        if not self.next_direction:
            return
            
        painter.save()
        
        # 배경 패널
        panel_rect = QRectF(center_x - 150, y - 25, 300, 50)
        
        panel_gradient = QLinearGradient(panel_rect.topLeft(), panel_rect.bottomRight())
        panel_gradient.setColorAt(0, QColor(30, 58, 95, 120))
        panel_gradient.setColorAt(1, QColor(6, 17, 32, 80))
        
        painter.setBrush(QBrush(panel_gradient))
        painter.setPen(QPen(QColor(0, 240, 255, 80), 1))
        painter.drawRoundedRect(panel_rect, 15, 15)
        
        # "다음" 라벨
        painter.setFont(QFont("Segoe UI", 10, QFont.Light))
        painter.setPen(QPen(QColor(160, 180, 204)))
        painter.drawText(center_x - 140, y - 10, "NEXT")
        
        # 다음 방향 텍스트
        painter.setFont(QFont("Segoe UI", 14, QFont.Light))
        painter.setPen(QPen(QColor(245, 245, 245)))
        
        next_text = self.next_direction
        if len(next_text) > 25:
            next_text = next_text[:25] + "..."
        
        painter.drawText(center_x - 140, y + 8, next_text)
        
        painter.restore()

    def update_navigation_info(self, instructions, current_speed=0, route_progress=0):
        self.speed = current_speed
        self.progress = route_progress

        if not instructions:
            self.current_direction = "경로를 설정하세요"
            self.current_distance = 0.0
            self.next_direction = ""
            self.update()
            return

        direction, distance = instructions[0]

        if distance > 5:
            self.current_direction = "직진"
            self.current_distance = distance
            if ("좌회전" in direction or "우회전" in direction or "목적지" in direction) and distance <= 50:
                self.next_direction = direction
            else:
                self.next_direction = ""
            self.update()
            return

        self.current_direction = direction
        self.current_distance = distance

        if len(instructions) > 1:
            next_dir, next_dist = instructions[1]
            if "목적지" in next_dir:
                self.next_direction = f"직진 {int(round(next_dist))}m 후 도착"
            else:
                self.next_direction = f"직진 {int(round(next_dist))}m"
        else:
            self.next_direction = ""

        self.update()

# ===================================================================
# 프리미엄 자동차 아이템
# ===================================================================
class PremiumCarItem(QGraphicsObject):
    positionChanged = pyqtSignal(QPointF)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.car_shape = QPolygonF([
            QPointF(-18, -10), QPointF(18, -10), QPointF(18, 10),
            QPointF(12, 14), QPointF(-12, 14), QPointF(-18, 10)
        ])
        
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setZValue(100)

    def boundingRect(self):
        return self.car_shape.boundingRect()

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 차량 본체 그라데이션
        car_gradient = QLinearGradient(-18, -10, 18, 14)
        car_gradient.setColorAt(0, QColor(0, 240, 255, 220))
        car_gradient.setColorAt(0.5, QColor(77, 166, 255, 200))
        car_gradient.setColorAt(1, QColor(30, 58, 95, 180))
        
        painter.setBrush(QBrush(car_gradient))
        painter.setPen(QPen(QColor(245, 245, 245), 2))
        painter.drawPolygon(self.car_shape)
        
        # 방향 표시
        painter.setPen(QPen(QColor(245, 245, 245), 3))
        painter.drawLine(QPointF(0, -8), QPointF(0, 8))
        painter.drawLine(QPointF(0, -8), QPointF(-4, -4))
        painter.drawLine(QPointF(0, -8), QPointF(4, -4))

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.positionChanged.emit(value)
        return super().itemChange(change, value)

# ===================================================================
# 프리미엄 주차장 UI
# ===================================================================
class PremiumParkingUI(QWidget):
    SCENE_W, SCENE_H = 2000, 2000
    CELL, MARGIN, PATH_WIDTH = 30, 10, 10
    PIXELS_PER_METER = 50
    ENTRANCE = QPointF(200, 200)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("HYUNDAI Premium Cluster Navigation")
        self.setGeometry(50, 50, 1800, 1000)
        
        # 프리미엄 클러스터 스타일 적용
        self.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {HYUNDAI_CLUSTER_COLORS['background_primary']}, 
                    stop:1 {HYUNDAI_CLUSTER_COLORS['background_secondary']});
                color: {HYUNDAI_CLUSTER_COLORS['text_primary']};
                font-family: 'Segoe UI';
                font-weight: 300;
            }}
            QLineEdit {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(30, 58, 95, 150),
                    stop:1 rgba(6, 17, 32, 100));
                border: 2px solid {HYUNDAI_CLUSTER_COLORS['neon_cyan']};
                border-radius: 15px;
                padding: 15px 20px;
                font-size: 14px;
                font-weight: 300;
                color: {HYUNDAI_CLUSTER_COLORS['text_primary']};
            }}
            QLineEdit:focus {{
                border: 3px solid {HYUNDAI_CLUSTER_COLORS['glow_blue']};
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(0, 240, 255, 40),
                    stop:1 rgba(30, 58, 95, 80));
            }}
            QLineEdit::placeholder {{
                color: {HYUNDAI_CLUSTER_COLORS['text_secondary']};
            }}
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {HYUNDAI_CLUSTER_COLORS['accent_blue']}, 
                    stop:1 {HYUNDAI_CLUSTER_COLORS['glow_blue']});
                border: 2px solid {HYUNDAI_CLUSTER_COLORS['neon_cyan']};
                border-radius: 18px;
                color: {HYUNDAI_CLUSTER_COLORS['warm_white']};
                font-size: 16px;
                font-weight: 300;
                padding: 18px 35px;
                min-height: 25px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {HYUNDAI_CLUSTER_COLORS['neon_cyan']}, 
                    stop:1 {HYUNDAI_CLUSTER_COLORS['glow_blue']});
                border: 3px solid {HYUNDAI_CLUSTER_COLORS['neon_cyan']};
            }}
            QPushButton:pressed {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {HYUNDAI_CLUSTER_COLORS['glow_blue']}, 
                    stop:1 {HYUNDAI_CLUSTER_COLORS['accent_blue']});
            }}
            QLabel {{
                color: {HYUNDAI_CLUSTER_COLORS['text_primary']};
                font-size: 14px;
                font-weight: 300;
            }}
            QGraphicsView {{
                border: 3px solid {HYUNDAI_CLUSTER_COLORS['neon_cyan']};
                border-radius: 20px;
                background: {HYUNDAI_CLUSTER_COLORS['background_primary']};
            }}
        """)

        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(30)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # 왼쪽 패널 - 지도
        left_panel = QWidget()
        left_panel.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(30, 58, 95, 120),
                    stop:1 rgba(6, 17, 32, 80));
                border: 2px solid {HYUNDAI_CLUSTER_COLORS['glow_blue']};
                border-radius: 25px;
            }}
        """)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(25)
        left_layout.setContentsMargins(25, 25, 25, 25)

        # 지도 뷰
        self.scene = QGraphicsScene(0, 0, self.SCENE_W, self.SCENE_H)
        self.scene.setItemIndexMethod(QGraphicsScene.NoIndex)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setViewportUpdateMode(QGraphicsView.MinimalViewportUpdate)
        self.view.scale(0.5, 0.5)
        self.view.scale(1, -1)
        self.view.translate(0, -self.SCENE_H)

        # 컨트롤 패널
        controls_frame = QWidget()
        controls_frame.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(0, 240, 255, 25),
                    stop:1 rgba(30, 58, 95, 15));
                border: 2px solid {HYUNDAI_CLUSTER_COLORS['neon_cyan']};
                border-radius: 20px;
                padding: 20px;
            }}
        """)
        controls_layout = QVBoxLayout(controls_frame)
        controls_layout.setSpacing(20)
        
        # 타이틀
        title_label = QLabel("목적지 설정")
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {HYUNDAI_CLUSTER_COLORS['neon_cyan']};
                font-size: 20px;
                font-weight: 300;
                margin-bottom: 15px;
            }}
        """)
        
        # 입력 필드들
        self.le1 = QLineEdit()
        self.le1.setPlaceholderText("목적지 좌표: 예)