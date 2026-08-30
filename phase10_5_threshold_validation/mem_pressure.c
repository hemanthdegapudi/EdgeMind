#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
    if (argc < 2) {
        printf("Usage: %s <MB to allocate>\n", argv[0]);
        return 1;
    }
    long mb = atol(argv[1]);
    long bytes = mb * 1024 * 1024;
    char *ptr = malloc(bytes);
    if (!ptr) {
        printf("Failed to allocate %ld MB\n", mb);
        return 1;
    }
    // Fill with pseudo-random data to prevent zRAM compression
    for (long i = 0; i < bytes; i++) {
        ptr[i] = (char)(i % 251);
    }
    printf("Allocated %ld MB. Sleeping indefinitely...\n", mb);
    while(1) {
        sleep(60);
    }
    return 0;
}
