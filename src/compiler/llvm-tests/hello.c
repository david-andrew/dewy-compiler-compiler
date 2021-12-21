#define SYS_write 1
#define SYS_exit 60
#define stdout 1
#define stderr 2

// write syscall:
//     %rax: syscall number, %rdi: file descriptor, %rsi: buffer, %rdx: number of bytes
//     %rax: return value
int write(char* buf, int len)
{
    int n;
    asm volatile("syscall\n" : "=A"(n) : "a"(SYS_write), "D"(stderr), "S"(buf), "d"(len));
    return n;
}

// void puts(char* s)
// {
//     int len = 0;
//     while (s[len]) len++;
//     write(s, len);
// }

// void puti(unsigned int i)
// {
//     const int buf_size = 32;
//     char buf[buf_size];
//     int len = 0;
//     do {
//         buf[buf_size - len++ - 1] = '0' + i % 10;
//         i /= 10;
//     } while (i > 0);
//     write(&buf[buf_size - len], len);
// }

// exit syscall:
//     %rax: syscall number, %rdi: exit code
void exit()
{
    // infinite loop until the system ends this process
    for (;;) asm volatile("syscall\n" : : "a"(SYS_exit), "D"(0));
}

// TODO->move to a separate file
int main()
{
    char buf[] = "Hello, World!\n";
    write(buf, sizeof(buf));
    return 0;
}

void _start()
{
    int res = main();
    exit(res);
}
