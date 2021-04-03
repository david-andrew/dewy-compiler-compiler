#ifndef REDUCTION_C
#define REDUCTION_C

#include <stdlib.h>
#include <stdio.h>
#include <inttypes.h>

#include "reduction.h"
#include "metaparser.h"
#include "utilities.h"
#include "ustring.h"


/**
 * Create a new rnglr reduction marker for the parser table.
 */
reduction* new_reduction(uint64_t head_idx, uint64_t length)
{
    reduction* r = malloc(sizeof(reduction));
    *r = (reduction){.head_idx=head_idx, .length=length};
    return r;
}


/**
 * Create an rnglr reduction wrapped in an object.
 */
obj* new_reduction_obj(reduction* r)
{
    obj* R = malloc(sizeof(obj));
    *R = (obj){.type=Reduction_t, .data=r};
    return R;
}


/**
 * Print out the value contained in the rnglr reduction.
 */
void reduction_str(reduction* r)
{
    printf("R(");
    obj* head = metaparser_get_symbol(r->head_idx);
    obj_str(head);
    printf(", %"PRIu64")", r->length);
}


/**
 * Return the printed width of the rnglr reduction action's string representation.
 */
int reduction_strlen(reduction* r)
{
    int width = 0;
    obj* head = metaparser_get_symbol(r->head_idx);
    width += ustring_len(head->data);
    width += snprintf("", 0, "R(, %"PRIu64")", r->length);
    return width;
}



/**
 * Print out the internal representation of the rnglr reduction.
 */
void reduction_repr(reduction* r)
{
    printf("reduction{head_idx: %"PRIu64", length: %"PRIu64"}", r->head_idx, r->length);
}


/**
 * Cheack if two rnglr reductions are equal.
 */
bool reduction_equals(reduction* left, reduction* right)
{
    return left->length == right->length && left->head_idx == right->head_idx;
}


/**
 * Compute a hash of the rnglr reduction.
 */
uint64_t reduction_hash(reduction* r)
{
    uint64_t seq[] = {r->length, r->head_idx};
    return hash_uint_sequence(seq, sizeof(seq) / sizeof(uint64_t));
}


/**
 * Free the rnglr reduction container.
 */
void reduction_free(reduction* r)
{
    free(r);
}


#endif