#ifndef USTRING_C
#define USTRING_C

#include <stdlib.h>
#include <stdio.h>

#include "ustring.h"
#include "utilities.h"


#define AUGMENT_CHAR 0x200000 //first invalid codepoint (2^21)


/**
 * Return a unicode substring converted from the given utf8 string.
 * Indices index the unicode output string, not the utf8 input string.
 * Does not use Dewy slicing rules, only positive in bounds indices.
 * `stop` and `start` bounds are inclusive
 */
uint32_t* ustring_charstar_substr(char* str, int start, int stop)
{
    //unicode string length (includes chars at start and stop)
    size_t length = stop - start + 1;

    //allocate uint32_t string with room for null terminator at the end
    uint32_t* substr = malloc((length + 1) * sizeof(uint32_t));

    //copy pointer for assigning each character
    uint32_t* ptr = substr;

    //throw away everything up to the start of the substring
    for (int i = 0; i < start; i++)
    {
        eat_utf8(&str);
    }
    //copy the substring to our unicode array
    for (int i = 0; i < length; i++)
    {
        *ptr++ = eat_utf8(&str);
    }
    *ptr = 0; //null terminator at the end of the string

    return substr;
}


/**
 * Return a unicode string converted from the given utf8 string.
 * Indices index the utf8 input string, not unicode output string.
 * Does not use Dewy slicing rules, only positive in bounds indices.
 * `stop` and `start` bounds are inclusive
 */
uint32_t* ustring_utf8_substr(char* str, int start, int stop)
{
    //get the utf8 substring
    char* raw_str = substr(str, start, stop);

    //compute number of unicode characters in string
    size_t length = utf8_length(raw_str);

    //get the unicode version of the string by taking a unicode substring of the whole length
    uint32_t* s = ustring_charstar_substr(raw_str, 0, length-1);
    
    //free the temporary raw string
    free(raw_str);

    return s;
}


/**
 * Return the length of the unicode string (not including the null terminater)
 */
size_t ustring_len(uint32_t* string)
{
    size_t length = 0;
    while (string[length]) { length++; }
    return length;
}


/**
 * Compare two unicode strings. 
 * Identical algorithm to normal char* strcmp.
 */
int64_t ustring_cmp(uint32_t* left, uint32_t* right)
{
    uint32_t l, r;
    do
    {
        l = *left++;
        r = *right++;
        if (l == 0) break;
    }
    while (l == r);
    return l - r;
}


/**
 * Clone a null terminated unicode string.
 */
uint32_t* ustring_clone(uint32_t* string)
{
    //get length of string
    size_t length = ustring_len(string);

    //perform copy
    uint32_t* copy = malloc((length + 1) * sizeof(uint32_t));
    uint32_t* ptr = copy;
    while ((*ptr++ = *string++));
    return copy;
}


/**
 * Read a hex string and convert to an unsigned integer
 */
uint64_t ustring_parse_hex(uint32_t* str)
{
    return ustring_parse_base(str, 16, hex_digit_to_value);
}


/**
 * Read a decimal string, and convert to an unsigned integer.
 */
uint64_t ustring_parse_dec(uint32_t* str)
{
    return ustring_parse_base(str, 10, dec_digit_to_value);
}


/**
 * Generic number parser for arbitrary base.
 */
uint64_t ustring_parse_base(uint32_t* str, uint64_t base, uint64_t (*base_digit_to_value)(char))
{
    size_t len = ustring_len(str);
    uint64_t pow = 1;
    uint64_t val = 0;
    for (int64_t i = len - 1; i >= 0; i--)
    {
        val += base_digit_to_value(str[i]) * pow;
        pow *= base;
    }
    return val;
}


/**
    print the unicode character to the terminal as UTF-8

    This function uses int8_t instead of uint8_t since putchar expects a signed value
*/
void put_unicode(uint32_t c)
{
    if (c < 0x80)                               //0xxxxxxx
    {   
        int8_t b0 = c & 0x7F;                   //c & 0b01111111
        putchar(b0);
    }
    else if (c < 0x800)                         //110xxxxx 10xxxxxx
    {
        int8_t b0 = (c & 0x3F) | 0x80;          //c & 0b10111111
        int8_t b1 = (c >> 6 & 0xDF) | 0xC0;     //c >> 6 & 0b11011111
        putchar(b1);
        putchar(b0);
    } 
    else if (c < 0x10000)                       //1110xxxx 10xxxxxx 10xxxxxx
    {
        int8_t b0 = (c & 0x3F) | 0x80;          //c & 0b10111111
        int8_t b1 = (c >> 6 & 0x3F) | 0x80;     //c >> 6 & 0b10111111
        int8_t b2 = (c >> 12 & 0x0F) | 0xE0;    //c >> 12 & 0b11101111
        putchar(b2);
        putchar(b1);
        putchar(b0);
    }
    else if (c <= 0x001FFFFF)                    //11110xxx 10xxxxxx 10xxxxxx 10xxxxxx
    {
        int8_t b0 = (c & 0x3F) | 0x80;          //c & 0b10111111
        int8_t b1 = (c >> 6 & 0x3F) | 0x80;     //c >> 6 & 0b10111111
        int8_t b2 = (c >> 12 & 0x3F) | 0x80;    //c >> 12 & 0b10111111
        int8_t b3 = (c >> 18 & 0x07) | 0xF0;    //c >> 18 & 0b11110111
        putchar(b3);
        putchar(b2);
        putchar(b1);
        putchar(b0);
    }
    else
    {
        printf("ERROR: invalid unicode codepoint \"%u\"\n", c);
    }
}


/**
    detect the next utf-8 character in str_ptr, and return it as a 32-bit codepoint.
    advance the str_ptr by the size of the detected utf-8 character
*/
uint32_t eat_utf8(char** str_ptr)
{
    uint8_t b0 = **str_ptr;
    (*str_ptr)++;

    if (!b0) //if this is a null terminator, return 0
    { 
        return 0; 
    }
    else if (b0 >> 7 == 0x00) //regular ascii character
    { 
        return b0; 
    }
    else if (b0 >> 5 == 0x06) //2 byte utf-8 character
    {   
        uint8_t b1 = **str_ptr;
        (*str_ptr)++;
        if (b1 >> 6 == 0x02)
        {
            return (b0 & 0x1F) << 6 | (b1 & 0x3F);
        }
    }
    else if (b0 >> 4 == 0x0E) //3 byte utf-8 character
    {
        uint8_t b1 = **str_ptr;
        (*str_ptr)++;
        if (b1 >> 6 == 0x02)
        {
            uint8_t b2 = **str_ptr;
            (*str_ptr)++;
            if (b2 >> 6 == 0x02)
            {
                return (b0 & 0x0F) << 12 | (b1 & 0x3F) << 6 | (b2 & 0x3F);
            }
        }
    }
    else if (b0 >> 3 == 0x1E) //4 byte utf-8 character
    {
        uint8_t b1 = **str_ptr;
        (*str_ptr)++;
        if (b1 >> 6 == 0x02)
        {
            uint8_t b2 = **str_ptr;
            (*str_ptr)++;
            if (b2 >> 6 == 0x02)
            {
                uint8_t b3 = **str_ptr;
                (*str_ptr)++;
                if (b3 >> 6 == 0x02)
                {
                    return (b0 & 0x07) << 18 | (b1 & 0x3F) << 12 | (b2 & 0x3F) << 6 | (b3 & 0x3F);
                }
            }
        }
    }
    
    printf("ERROR: eat_utf8() found ill-formed utf-8 character\n");
    return 0;
}


/**
 * Return an allocated null terminated unicode string containing the given character.
 */
uint32_t* ustring_from_unicode(uint32_t c)
{
    uint32_t* str = malloc(2*sizeof(uint32_t));
    str[0] = c;
    str[1] = 0;
    return str;
}


/**
 * Return the unicode character at the given index in the utf8 string. `str_ptr` is not modified.
 */
uint32_t peek_unicode(char** str_ptr, size_t index, size_t* delta)
{
    char* str = *str_ptr;
    char** str_ptr_copy = &str;
    uint32_t c;
    for (size_t i = 0; i <= index; i++)
    {
        c = eat_utf8(str_ptr_copy);
    }
    if (delta != NULL) *delta = *str_ptr_copy - *str_ptr;
    return c;
}

/**
 * Compute the unicode length of the given utf8 string.
 */
size_t utf8_length(char* str)
{
    size_t i = 0;
    while (eat_utf8(&str)) { i++; };
    return i;
}


/**
    print the unicode character, or a special character for some special inputs
*/
void unicode_str(uint32_t c)
{
    if (c == 0)                 //null character. represents an empty string/set
    {
        put_unicode(0x2300);    // ⌀ (diameter symbol)
    }
    else if (c == AUGMENT_CHAR) // represents the end of a meta-rule
    {
        put_unicode(0x1F596);    // 🖖 (vulcan salute). easy to spot character
    }
    else                        //any other unicode character
    {
        put_unicode(c);
    }
}


/**
 * Print out the character or hex value of the given char.
 */
void unicode_ascii_or_hex_str(uint32_t c)
{
    if (0x21 <= c && c <= 0x7E) put_unicode(c);
    else printf("\\x%X", c);
}


void ustring_str(uint32_t* s)
{
    uint32_t c;
    while ((c = *s++)) put_unicode(c);
}


void unicode_string_repr(uint32_t* s)
{    
    // putchar('"');
    printf("U\"");
    ustring_str(s);
    putchar('"');
}


/**
 * Return the literal unicode represented by the escape char
 * Recognized escaped characters are \n \r \t \v \b \f and \a
 * all others just put the second character literally 
 * Common such literals include \\ \' \" \[ \] and \-
 */
uint32_t escape_to_unicode(uint32_t c)
{
    switch (c)
    {
        // recognized escape characters
        case 'a': return 0x7;   // bell
        case 'b': return 0x8;   // backspace
        case 't': return 0x9;   // tab
        case 'n': return 0xA;   // new line
        case 'v': return 0xB;   // vertical tab
        case 'f': return 0xC;   // form feed
        case 'r': return 0xD;   // carriage return
        
        // non-recognized escapes return the literal character
        default: return c;
    }
}

#endif