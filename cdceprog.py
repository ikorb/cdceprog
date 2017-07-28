#!/usr/bin/python
#
# cdceprog.py: A quick hack to program a CDCE913/925 on an I2C bus of a Linux system
#
#  Copyright (C) 2015-2017, Ingo Korb <ingo@akana.de>
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#   1. Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#   2. Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
#  ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
#  LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
#  CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
#  SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
#  INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
#  CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
#  ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF
#  THE POSSIBILITY OF SUCH DAMAGE.

import base64
import smbus
import sys
import time

class CDCEPLL:
    def __init__(self, name, address, register_count):
        self.name           = name
        self.address        = address
        self.register_count = register_count

# FIXME: there should be command-line options for this
cdce913 = CDCEPLL("CDCE 913", 0x65, 0x20)
cdce925 = CDCEPLL("CDCE 925", 0x64, 0x30)

all_plls = [cdce913, cdce925]

# read data file
if len(sys.argv) != 2:
    print("Usage: {} hexfile".format(sys.argv[0]))
    exit(2)

pllregs = {}

fd = open(sys.argv[1], "r")
for line in fd:
    if not line.startswith(":"):
        print("No start character found in {}".format(line))
        exit(2)

    data = bytearray.fromhex(line.rstrip().lstrip(":"))
    bytecount = data[0]
    addr      = (data[1] << 8) | data[2]
    # FIXME: Verify checksum
    if data[3] == 0:
        # copy data
        for i in xrange(0, bytecount):
            pllregs[addr + i] = data[i + 4]
    elif data[3] == 1:
        # end marker, do nothing
        pass
    else:
        print("ERROR: Unknown record type {:d} found".format(data[3]))

fd.close()

# determine PLL type based on highest register used
current_pll = None
pll_regcount = max(pllregs.keys()) + 1

for pll in all_plls:
    if pll.register_count == pll_regcount:
        current_pll = pll

if current_pll == None:
    print("ERROR: No PLL type with {} registers known".format(pll_regcount))
    exit(2)

print("Found data for a {} chip".format(current_pll.name))

# clear EEPROM lock and write bits
pllregs[1] = pllregs[1] & ~(1 << 5)
pllregs[6] = pllregs[6] & ~(1 << 0)

# change device address in data to default for the chip
if (pllregs[1] & 3) != (current_pll.address & 3):
    print("WARNING: Non-default I2C address in hex file ignored")
    pllregs[1] = (pllregs[1] & ~3) | (current_pll.address & 3)

# FIXME: Very old Raspis have I2C0 on the GPIO header
bus = smbus.SMBus(1)

# check if device is present by reading byte 0
try:
    res = bus.read_byte_data(current_pll.address, 0x80)
except IOError as e:
    print("I/O error({0}): {1}".format(e.errno, e.strerror))
    print("(maybe the PLL is not connected?)")
    exit(2)

# write PLL settings
for i in xrange(0x10, current_pll.register_count):
    if pllregs[i] != None:
        bus.write_byte_data(current_pll.address, 0x80 + i, pllregs[i])

# write control register settings
for i in xrange(0, 0x10):
    if pllregs[i] != None:
        bus.write_byte_data(current_pll.address, 0x80 + i, pllregs[i])

# initiate EEPROM write
bus.write_byte_data(current_pll.address, 0x86, pllregs[6] | 1)

# wait until write is finished
while bus.read_byte_data(current_pll.address, 0x81) & (1 << 6):
    print("Waiting until EEPROM write cycle finishes...")
    time.sleep(0.1)

