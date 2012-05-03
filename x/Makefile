xdisp: ledwand.o xdisp.c ledwand.h
	gcc -g -O3 -o $@ ledwand.o xdisp.c

ledwand.o: ledwand.c ledwand.h
	gcc -g -O3 -c -o $@ $<

clean:
	rm -f *.o xdisp
