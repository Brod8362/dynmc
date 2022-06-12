#include <stdio.h>
#include <inttypes.h>

#define SEGMENT_BITS 0x7F
#define CONTINUE_BIT 0x80

int32_t read_var_int(uint8_t* buf, size_t* idx) {
    int32_t value = 0;
    size_t pos = 0;
    uint8_t byte;
    while (1) {
        byte = buf[*idx++];
        value |= (byte & SEGMENT_BITS) << pos;
        if ((byte & CONTINUE_BIT) == 0) break;
        pos += 7;
        if (pos >= 32) {
            //TODO throw exception here
        } 
    }
    return value;
}

int64_t read_var_long(uint8_t* buf, size_t* idx) {
    int64_t value = 0;
    size_t pos = 0;
    uint8_t byte;
    while (1) {
        byte = buf[*idx++];
        value |= (long) (byte & SEGMENT_BITS) << pos;
        if ((byte & CONTINUE_BIT) == 0) break;
        pos += 7;
        if (pos >= 64) {
            //TODO throw exception here
        } 
    }
    return value;
}