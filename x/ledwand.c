#include "ledwand.h"

int ledwand_init(Ledwand *ledwand){

    if(ledwand == NULL){
        ledwand = malloc(sizeof(*ledwand));
    }

    bzero(&ledwand->s_addr, sizeof(ledwand->s_addr));
    ledwand->s_addr.sin_family = AF_INET;
    ledwand->s_addr.sin_port = htons(2342);
    if(!inet_aton(LEDWAND_IP, &ledwand->s_addr.sin_addr)){
        perror("inet_aton failed\n");
        return -1;
    }

    if((ledwand->s_sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)) == -1){
        perror("socket failed\n");
        return -1;
    }

    return 0;
}

void ledwand_send(const Ledwand *ledwand,
                  const uint16_t cmd,
                  const uint16_t xpos,
                  const uint16_t ypos,
                  const uint16_t xsize,
                  const uint16_t ysize,
                  const uint8_t *text,
                  const uint32_t text_len)
{

    uint8_t buf[LEDWAND_BUFSIZE];

    Request request;
    request.cmd = cmd;
    request.xpos = xpos;
    request.ypos = ypos;
    request.xsize = xsize;
    request.ysize = ysize;

    int len = sizeof(request);

    if(text_len > (LEDWAND_BUFSIZE - text_len)){
        perror("ERROR: Textlen bigger than buflen\n");
        return;
    }

    memcpy(&buf, &request, len);
    if(text != NULL){
        memcpy(&buf[len], text, text_len);
        len += text_len;
    }

    if(sendto(ledwand->s_sock, buf, len, 0, (struct sockaddr*)&ledwand->s_addr, sizeof(ledwand->s_addr)) <= 0){
        perror("Send failed\n");
    }
}

void ledwand_draw_buffer(const Ledwand *ledwand, const uint8_t *buf, const uint32_t buflen){

    uint32_t i = LEDWAND_PARTS, step = 0;
    do{
        ledwand_send(ledwand, LED_DRAW, step, LEDWAND_PARTSIZE, 0, 0, buf+step, step);
        step += LEDWAND_PARTSIZE;
        usleep(500);
    } while(--i);
}

void ledwand_clear(const Ledwand *ledwand){
    ledwand_send(ledwand, CLEAR, 0, 0, 0, 0, NULL, 0);
}

void ledwand_set_brightness(const Ledwand *ledwand, const uint8_t brightness){
    ledwand_send(ledwand, SET_BRIGHTNESS, 0, 0, 0, 0, &brightness, sizeof(brightness));
}

void ledwand_draw_image(const Ledwand *ledwand, uint8_t *buffer, const uint32_t buf_len){

    if(buf_len != (LEDWAND_PIXEL_X * LEDWAND_PIXEL_Y)){
        printf("Buffer size (%d) should be 448*240\n", buf_len);
        return;
    }

    uint32_t i = 0, j = 0;

/*    uint8_t tempbuf[((LEDWAND_PIXEL_X * LEDWAND_PIXEL_Y)/8)];

    uint8_t oldpixel;
    int16_t diff;

    do{
        oldpixel = buffer[i];
        tempbuf[i>>3] |= (oldpixel > LEDWAND_BIAS) << (7-(i%8));
        diff = (oldpixel > LEDWAND_BIAS) ? oldpixel - 255 : oldpixel;
        buffer[i+1] += (uint8_t)(7 * diff / 16);
        buffer[i+(LEDWAND_PIXEL_X)-1] += (uint8_t)(3 * diff / 16);
        buffer[i+(LEDWAND_PIXEL_X)] += (uint8_t)(5 * diff / 16);
        buffer[i+(LEDWAND_PIXEL_X)+1] += (uint8_t)(diff / 16);

    }while((++i) <(LEDWAND_PIXEL_X * (LEDWAND_PIXEL_Y - 1)));

    do{
        oldpixel = buffer[i];
        tempbuf[i>>3] |= (oldpixel > LEDWAND_BIAS) << (7-(i%8));
        diff = (oldpixel > LEDWAND_BIAS) ? oldpixel - 255 : oldpixel;
        buffer[i+1] += (uint8_t)(7 * diff / 16);

    }while((++i) < ((LEDWAND_PIXEL_X * LEDWAND_PIXEL_Y)-1));*/

    static signed short tmpbuffer[448*240+500];

    //size_t *p1 = (size_t*)tmpbuffer;
    //size_t *p2 = (size_t*)buffer;
    for(i = 0; i < (448*240); i++){
    /*for(i = 0; i < (448*240)/(sizeof(size_t)); i++){
        p1[i] = p2[i];
    }*/
        tmpbuffer[i] = buffer[i];
    }
    bzero(buffer, buf_len);

    int row = 0, column = 0;
    int16_t oldpixel = 0;
    uint8_t newpixel = 0;
    signed short diff = 0;

    /*do{
        oldpixel = tmpbuffer[i];
        buffer[i] |= (oldpixel > LEDWAND_BIAS) << (7-(column%8));

    }while((++i) < (LEDWAND_PIXEL_X * (LEDWAND_PIXEL_Y - 1)));
    */

	for (row = 0; row < 240; row++)
	{
		for (column = 0; column < 448; column++)
		{
			oldpixel = tmpbuffer[row*448+column];

			newpixel = (oldpixel > LEDWAND_BIAS) << (7-(column%8));
			buffer[row*56+column/8] |= newpixel;

			newpixel = (oldpixel > LEDWAND_BIAS) ? 255 : 0;

			diff = oldpixel - newpixel;

			// floyd steinberg dithering
			tmpbuffer[row*448+(column+1)] += 7 * diff / 16;
            tmpbuffer[(row+1)*448+(column-1)] += 3 * diff / 16;
			tmpbuffer[(row+1)*448+column] += 5 * diff / 16;
			tmpbuffer[(row+1)*448+(column+1)] += 1 * diff / 16;
		}
	}

    for(i = 0, j = 0; i < 448*29; i+= 448+4*56, j+= 448){
        ledwand_send(ledwand, 18, j, 448, 0, 0, &buffer[i], 448);
        usleep(400);
    }
}
