from ordered_set import T
from r2a.ir2a import IR2A
from player.parser import *
import time
from statistics import mean
import math

class R2AFDASH(IR2A):

    def __init__(self, id):
        IR2A.__init__(self, id)
        self.throughputs = []
        self.request_time = 0
        self.qi = []
        self.idx_qi_current = 0
        self.idx_qi_previous = 0
        self.buffer_size_current = 0
        self.buffer_size_previous = 0
        self.first = True

        

    def handle_xml_request(self, msg):
        self.request_time = time.perf_counter()
        self.send_down(msg)

    def handle_xml_response(self, msg):
        # Get qualities
        parsed_mpd = parse_mpd(msg.get_payload())
        self.qi = parsed_mpd.get_qi()

        # variation time between request time and the real time
        variation_time = time.perf_counter() - self.request_time
        bit_length = msg.get_bit_length()

        # add to list throughputs 
        self.throughputs.append(bit_length / variation_time)

        self.send_up(msg)

    def handle_segment_size_request(self, msg):
        # real time request
        self.request_time = time.perf_counter()


        if not self.first:

            buffer_list = self.whiteboard.get_playback_buffer_size()

            # update the last buffer size
            self.buffer_size_previous = self.buffer_size_current

            # update the current buffer size
            self.buffer_size_current = buffer_list[-1][1]-1

            # target buffering time = 35
            SHORT, LONG, CLOSE = [False, False, False]
            FALLING, STEADY, RISING = [False, False, False]

            if self.buffer_size_current < 35:
                SHORT = True
            elif self.buffer_size_current >= 50:
                LONG = True
            else:
                CLOSE = True

            delta_buffer_size = self.buffer_size_current - self.buffer_size_previous
            if delta_buffer_size < 0:
                FALLING = True
            elif delta_buffer_size > 0:
                RISING = True
            else:
                STEADY = True

            r1, r2, r3, r4, r5, r6, r7, r8, r9 = [0, 0, 0, 0, 0, 0, 0, 0, 0]
            
            if SHORT and FALLING:
                r1 = 1
            elif CLOSE and FALLING:
                r2 = 1
            elif LONG and FALLING:
                r3 = 1
            elif SHORT and STEADY:
                r4 = 1
            elif CLOSE and STEADY:
                r5 = 1
            elif LONG and STEADY:
                r6 = 1
            elif SHORT and RISING:
                r7 = 1
            elif CLOSE and RISING:
                r8 = 1
            elif LONG and RISING:
                r9 = 1

            # Increase
            I = math.sqrt(r9**2)
            # Small Increase
            SI = math.sqrt(r6**2 + r8**2)
            # No Changes
            NC = math.sqrt(r3**2 + r5**2 + r7**2)
            # Small Reduce
            SR = math.sqrt(r2**2 + r4**2)
            # Reduce
            R = math.sqrt(r1**2)

            # Factors of the output membership functions
            N2, N1, Z, P1, P2 = [0.25, 0.5, 1, 1.5, 2]

            # F represents an increase/decrease factor of the resolution of the next segment
            F = (N2 * R + N1 * SR + Z * NC + P1 * SI + P2 * I)/(SR + R + NC + SI + I)

            # K represents the last throughputs to analyze
            K = 4

            # Take the average of the last K throughputs
            media = 0
            step = 1
            for ri in self.throughputs[::-1]:
                media += ri

                step += 1
                if step == K:
                    break
            media /= K

            b_next = F*media

            self.idx_qi_current = 0
            for quality in self.qi:
                if self.idx_qi_current != 19:
                    if quality < b_next:
                        self.idx_qi_current += 1


            # Last throughput
            media_throughput = self.throughputs[-1]/K
            quality_current = self.qi[self.idx_qi_current]
            quality_previous = self.qi[self.idx_qi_previous]

            # verify qualities
            self.predict_current_buffer = self.buffer_size_current + (media_throughput/quality_current)*60
            self.predict_previous_buffer = self.buffer_size_current + (media_throughput/quality_previous)*60

            if quality_current > quality_previous and self.predict_current_buffer < 35:
                self.idx_qi_current = self.idx_qi_previous
            elif quality_current < quality_previous and self.predict_previous_buffer > 35:
                self.idx_qi_current = self.idx_qi_previous
            
            self.idx_qi_previous = self.idx_qi_current

        else:
            self.first = False
        
        selected_qi = self.qi[self.idx_qi_current]
        msg.add_quality_id(selected_qi)
        self.send_down(msg)

    def handle_segment_size_response(self, msg):
        # variation time between request time and the real time
        variation_time = time.perf_counter() - self.request_time
        bit_length = msg.get_bit_length()

        # add to list throughputs 
        self.throughputs.append(bit_length / variation_time)

        self.send_up(msg)

    def initialize(self):
        pass

    def finalization(self):
        pass
