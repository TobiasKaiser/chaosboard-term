#include <fcntl.h>
#include <sys/types.h>
#include <sys/mman.h>
#include <stdio.h>
#include <unistd.h>
#include <stdint.h>
#include "ledwand.h"

static uint8_t *xwd_file;
static size_t xwd_size;

#define FRAME_H 240
#define FRAME_W 448
static uint8_t grey_fb[FRAME_H][FRAME_W];
static struct Ledwand ledwand;

static void update_frame(void) {
    int row, col;
    uint32_t *input_fb=(uint32_t *)(xwd_file+xwd_size-(FRAME_H*FRAME_W*4));
    if((void*)input_fb<(void*)xwd_file) {
        fprintf(stderr, "Error: Illegal input file size.\n");
        exit(1);
    }
    msync(xwd_file, xwd_size, MS_SYNC); 
    for(row=0;row<FRAME_H;row++) {
        for(col=0;col<FRAME_W;col++) {
            uint32_t p32=input_fb[row*FRAME_W+col];
            grey_fb[row][col]=
                ((p32>>0)&0xff)*0.3
               +((p32>>8)&0xff)*0.3
               +((p32>>16)&0xff)*0.3;
        }
    }
    ledwand_draw_image(&ledwand, (uint8_t *) grey_fb, sizeof grey_fb);
}

int main(int argc, char *argv[]) {
    if(argc!=2) {
        fprintf(stderr, "Usage: %s XWD_FILE\n\n", argv[0]);
        exit(1);
    }
    int fd=open(argv[1], O_RDONLY);
    if(fd==-1) {
        fprintf(stderr, "Error: Cannot open file\n", argv[0]);
        exit(1);
    }
    FILE *f=fdopen(fd, "r");

    fseek(f, 0, SEEK_END);
    xwd_size=ftell(f);
    fseek(f, 0, SEEK_SET);
    
    ledwand_init(&ledwand);
    xwd_file=mmap(NULL, xwd_size, PROT_READ, MAP_SHARED, fd, 0);

    for(;;) {
        update_frame();
        printf(".");
        fflush(stdout);
        usleep(1000000/30);
    }
    munmap(xwd_file, xwd_size);
    return 0; 
}
