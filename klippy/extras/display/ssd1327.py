# Support for SSD1327 128x128 graphics LCD displays
#
# Copyright (C) 2019  John Jardine <john@gprime.net>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging, uc1701

# The SSD1327 supports both i2c and "4-wire" spi
class SSD1327(uc1701.DisplayBase):
    def __init__(self, config):
        self.screen_height = 128

        cs_pin = config.get("cs_pin", None)
        if cs_pin is None:
            io = uc1701.I2C(config, 60)
        else:
            io = uc1701.SPI4wire(config, "dc_pin")
        uc1701.DisplayBase.__init__(self, io)
    def flush(self):

        # Find all differences in the framebuffers and send them to the chip
        for new_data, old_data, page in self.all_framebuffers:
            if new_data == old_data:
                continue

            # collect diff in pairs
            diffs = [[i, 2] for i in range(0, len(new_data), 2)
                    if new_data[i] != old_data[i] or new_data[i+1] != old_data[i+1]]

            # Batch together changes that are close to each other
            for i in range(len(diffs)-2, -1, -1):
                pos, count = diffs[i]
                nextpos, nextcount = diffs[i+1]
                if pos + 5 >= nextpos and nextcount < 8:
                    diffs[i][1] = nextcount + (nextpos - pos)
                    del diffs[i+1]

            # Transmit changes
            for col_pos, count in diffs:
                row_start = page * 8
                row_end = row_start + 7
                self.send([0x75, row_start, row_end])
                col_start = col_pos // 2
                col_end = col_start + (count//2) - 1
                self.send([0x15, col_start, col_end])
                snd_data = self.frames_8_to_32(new_data[col_pos:col_pos+count])
                self.send(snd_data, True)
            old_data[:] = new_data

    def frames_8_to_32(self, frames):
        buf = bytearray()
        for i in range(0, len(frames), 2):
            buf.extend(self.frames_8_to_32_pair(frames[i:i+2]))
        return buf

    def frames_8_to_32_pair(self, frames):
        pix_num = 0
        buf = [0] * (len(frames) * 4)
        for frame_height in range(0, 8):
            for fnum, frame in enumerate(frames):
                if (frame >> frame_height) & 0x01:
                    if pix_num % 2 == 0: # 0=nibble order
                        buf[pix_num // 2] |= 0xF0
                    else:
                        buf[pix_num // 2] |= 0x0F
                pix_num += 1
        return buf

    def get_dimensions(self):
        return (16, 6)

    def init(self):
        init_cmds = [
            0xfd, 0x12,  # Unlock
            0xae,        # Display off
            0xa8, 0x5f,  # Multiplex ratio 0x05f * 1/64 duty
            0xa1, 0x00,  # Set display start line
            0xa2, 0x10,  # Display offset, shift mapping ram counter
            0xa0, 0x55,  # Remap configuration (was 0x51)
            # TODO: Make configurable. Also be careful here!!
            #0xab, 0x01,  # Enable internal VDD regulator (RESET)
            # TODO: Have contrast configurable?
            0x81, 0x80,  # Contrast, brightness, 0..128
            0xb1, 0x51,  # Phase length
            0xb3, 0x01,  # Set display clock divide ratio/oscillator frequency
            0xb9,        # Use linear lookup table
            #0xbc, 0x08,  # Pre-charge voltage level
            0xbe, 0x07,  # VCOMH voltage
            0xb6, 0x01,  # Second precharge
            #0xd5, 0x62,  # Enable second precharge, internal vsl (bit0 = 0) 
            0xA4,        # Normal display mode
            0xAF         # Display on
        ]
        self.send(init_cmds)
