#ifndef __LABELER__
#define __LABELER__

//#include <stdio.h>
#include <stdlib.h>

/**
 * Class containing image mask
 */
typedef struct {
    unsigned int width;
    unsigned int height;
    unsigned int max_grey_value;
    unsigned int **mask;
    double **data;
} image;

/**
 * Clears memory taken by given image
 * @param img
 */
//void free_image(image **img);

/**
 * Checks whether given x and y coordinates
 * lie within image bounds
 * @param x
 * @param y
 * @param w
 * @param h
 * @return True (1) if given coordinates are within
 *         image bounds, False (0) otherwise
 */
int in_bounds(int x, int y, int w, int h);

/**
 * Finds a root element of a disjoint set,
 * that the given item is located in
 * @param roots
 * @param item
 * @return A root element of a disjoint set
 */
unsigned int find_root(unsigned int *roots, unsigned int item);

/**
 * Performs a union on two disjoint sets
 * Disjoint set with a greater root element
 * is united under the other disjoint set
 * @param roots
 * @param x
 * @param y
 */
void unite_sets(unsigned int *roots, unsigned int x, unsigned int y);

/**
 * Labels components in given image with distinct grey colors
 * @param img
 * @return Exit code
 */
int label_components(image *img, double thr);

#endif // __LABELER__
