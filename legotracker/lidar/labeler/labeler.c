#include "labeler.h"

/**
 * Clears memory taken by image line by line,
 * then clears image mask pointer and finally
 * the image itself
 * @param img
 */
//void free_image(image **img) {
//    int y;
//    int image_height = (*img)->height;
//
//    // free each image line
//    for (y = 0; y < image_height; y++) {
//        free((*img)->mask[y]);
//    }
//
//    free((*img)->mask);
//    free((*img));
//    *img = NULL;
//}

/**
 * Given x and y coordinates lie within the image
 * if both are not negative and x is smaller than
 * image width and y is smaller than image height
 * @param x
 * @param y
 * @param w
 * @param h
 * @return True (1) if given coordinates are within
 *         image bounds, False (0) otherwise
 */
int in_bounds(int x, int y, int w, int h) {
    return x >= 0 && x < w && y >= 0 && y < h;
}

/**
 * Recursively finds a root element of a disjoint set,
 * parent is found when roots[item] and item are the same
 * @param roots
 * @param item
 * @return Root of item's disjoint set
 */
unsigned int find_root(unsigned int *roots, unsigned int item) {
    unsigned int parent = roots[item];

    // if parent is the same as item, we found the set root,
    // else try to look recursively up the tree until we find root
    return parent == item ? item : find_root(roots, parent);
}

/**
 * Unites two sets, the set with greater root value
 * is added to the other set (with smaller root value)
 * @param roots
 * @param x
 * @param y
 */
void unite_sets(unsigned int *roots, unsigned int x, unsigned int y) {
    unsigned int root_x = find_root(roots, x);
    unsigned int root_y = find_root(roots, y);

    // set the root with bigger index to the value
    // of the root with smaller index
    if (root_x < root_y) {
        roots[root_y] = roots[root_x];
    } else if (root_x > root_y) {
        roots[root_x] = roots[root_y];
    }

    // nothing is done when root_x == root_y because
    // that means they both are already in the same set
}

/**
 * Colors image components with distinct grey colors
 * using disjoint sets and performing union finds
 * A mask is applied to each image pixel and if any
 * grey or white (not black) pixels are found in the mask,
 * current pixel is colored with a color of one of mask
 * pixels and all mask pixels' colors are united (belong to one component)
 * After that, each pixel is looped through again and
 * its value is set to the value of its distinct set's
 * root element and maximal grey value of image is found
 * @param image
 * @return Colored image
 */
int label_components(image *image, double thr) {
    unsigned int neighbors[4];   // array of mask pixel colors
    unsigned int set_index = 1;  // starts at 1 because color 0 is black, not grey
    unsigned int neighbor_index = 0;
    unsigned int sets[1000000];    // array of disjoint set roots
    unsigned int i;

    // initialize all items as their own distinct sets
    for (i = 0; i < 1000000; i++) {
        sets[i] = i;
    }

    // all directions to get mask pixels from current
    // pixel in a format of [x_offset, y_offset] clockwise
    int mask[4][2] = {{-1, 0}, {-1, -1}, {0, -1}, {1, -1}};

    int x, mx, y, my, m;
    double center_data, neighbor_data;
    unsigned int neighbor, color = 1;
    unsigned int root;
    unsigned int max_grey_value;

    // first image pass
    for (y = 0; y < (int)(image->height); y++) {
        for (x = 0; x < (int)(image->width); x++) {

            // pixel is black, skip it because
            // it doesn't need to be labelled
            if (image->mask[y][x] == 0) {
                continue;
            }
            center_data = image->data[y][x];

            // clear a table of neighboring colors
            neighbor_index = 0;

            // all mask pixels
            for (m = 0; m < 4; m++) {
                mx = x + mask[m][0];
                my = y + mask[m][1];

                if (!in_bounds(mx, my, image->width, image->height)) {
                    continue;
                }

                // if this mask pixel is not black, add it as a current pixel neighbor
                neighbor = image->mask[my][mx];
                if (neighbor) {
                    neighbor_data = image->data[my][mx];

                    if (abs(center_data - neighbor_data) < thr) {
                        neighbors[neighbor_index] = neighbor;
                        neighbor_index++;
                    }
                }
            }

            // if current pixel has a colored (non-black) neighbor pick the first one
            // else select a new previously not used color
            if (neighbor_index != 0) {
                image->mask[y][x] = neighbors[0];
            } else {
                sets[set_index++] = color;
                image->mask[y][x] = color;
                color++;
            }

            // unite all colors found in this step, pixel color and mask pixel colors
            for (i = 0; i < neighbor_index; i++) {
                neighbor = neighbors[i];
                unite_sets(sets, image->mask[y][x], neighbor);
            }
        }
    }

    // second image pass
    // set color of each pixel to the value of its disjoint set root
    // and find the maximal grey pixel value
    max_grey_value = 0;
    for (y = 0; y < (int)(image->height); y++) {
        for (x = 0; x < (int)(image->width); x++) {
            root = find_root(sets, image->mask[y][x]);
            image->mask[y][x] = root;

            if (root > max_grey_value) {
                max_grey_value = root;
            }
        }
    }

    image->max_grey_value = max_grey_value;

    return EXIT_SUCCESS;
}
