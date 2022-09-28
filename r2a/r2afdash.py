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
        self.T = 35

        

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
            self.buffer_size_current = buffer_list[-1][1]


            
            SHORT, CLOSE, LONG = self.get_buff_var_size()
            FALLING, STEADY, RISING = self.get_buff_var_diff()
            
            r1 = min(SHORT , FALLING)
            r2 = min(CLOSE , FALLING)
            r3 = min(LONG , FALLING)
            r4 = min(SHORT , STEADY)
            r5 = min(CLOSE , STEADY)
            r6 = min(LONG , STEADY)
            r7 = min(SHORT , RISING)
            r8 = min(CLOSE , RISING)
            r9 = min(LONG , RISING)

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
            K = 3

            # Take the average of the last K throughputs
            media = 0
            last_throughputs = self.throughputs[::-1]
            last_k_throughputs = []

            for x in range(min(len(last_throughputs), K)):
                last_k_throughputs.append(last_throughputs[x])
                                                 
            media = mean(last_k_throughputs)

            b_next = F*media

            b_n = self.qi[0]
            self.idx_qi_current = 0
            n = len(self.qi)
            for i in range(len(self.qi)):
                if self.qi[n-i-1] < b_next:
                    b_n = self.qi[n-i-1]
                    self.idx_qi_current = n-i-1
                    break

            b_i = self.qi[self.idx_qi_previous]

            # verify qualities
            self.predict_current_buffer = self.buffer_size_current + (media/b_n)*60
            self.predict_previous_buffer = self.buffer_size_current + (media/b_i)*60
            
            if (b_n > b_i and self.predict_current_buffer < self.T):
                self.idx_qi_current = self.idx_qi_previous
            elif (b_n < b_i and self.predict_previous_buffer > self.T):
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
    

    def get_buff_var_size(self):
        buffer_list = self.whiteboard.get_playback_buffer_size()

        self.buffer_size_current = buffer_list[-1][1]
        self.buffer_size_previous = self.buffer_size_current
        T = self.T
        buffer = self.buffer_size_current
        SHORT, CLOSE, LONG = [0, 0, 0]

        if buffer <= 2*T/3:
            SHORT = 1
        elif buffer > T:
            SHORT = 0
        else:
            SHORT = -3 / T * buffer + 3
        
        if buffer < 2*T/3 or buffer > 4*T:
            CLOSE = 0
        elif buffer < T:
            CLOSE = 3/T*buffer-2
        else:
            CLOSE = -buffer/3*T + 4/3
        
        if buffer > 4*T:
            LONG = 1
        elif buffer < T:
            LONG = 0
        else:
             LONG = buffer/3*T -1/3
        
        return SHORT, CLOSE, LONG
    
    def get_buff_var_diff(self):
        delta_buffer_size = self.buffer_size_current - self.buffer_size_previous
        FALLING, STEADY, RISING = [0, 0, 0]
        T = self.T
        LEFT = -2*T/3
        MID = 0
        RIGHT = 4*T
        if delta_buffer_size < LEFT:
            FALLING = 1
        elif delta_buffer_size > MID:
            FALLING = 0
        else:
            FALLING = -3/(2*T) * delta_buffer_size
        
        if delta_buffer_size < LEFT or delta_buffer_size > RIGHT:
            STEADY = 0
        elif delta_buffer_size < MID:
            STEADY = -3/(2*T) * delta_buffer_size
        else:
            STEADY = -delta_buffer_size/(4*T) +1
        
        if delta_buffer_size < MID:
            RISING = 0
        elif delta_buffer_size > RIGHT:
            RISING = 1
        else:
            RISING = delta_buffer_size/(RIGHT)
        

        return FALLING, STEADY, RISING

    def initialize(self):
        pass

    def finalization(self):
        pass
