import os
import cv2
import glob
import json
import pickle
import joblib
import numpy as np
import matplotlib.pyplot as plt

N, M = 11, 8
criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)


def extract_images(filename, outdir, step=5):
    os.makedirs(outdir, exist_ok=True)
    vid = cv2.VideoCapture(filename)
    i, ret = 0, True
    while ret:
        ret, frame = vid.read()
        if ret:
            print("read", i)
            if i % step == 0:
                print("save", i)
                cv2.imwrite(outdir + str(i) + ".jpg", frame)
            i += 1
    vid.release()


def detect_single_chessboard(filename, resize=False, n=N, m=M, plot=True):
    img = cv2.imread(filename)
    if resize:
        img = cv2.resize(img, (img.shape[1] // 4, img.shape[0] // 4))

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    ret, corners = cv2.findChessboardCorners(gray, (n, m), None)

    if ret == True:
        corners2 = cv2.cornerSubPix(gray, corners, (n, m), (-1, -1), criteria)
        print(filename, img.shape, "Succeeded")
        print(corners, corners2, ret)

        if plot:
            img = cv2.drawChessboardCorners(img, (n, m), corners2, ret)
            cv2.imshow('img', img)
            while cv2.getWindowProperty('img', 0) >= 0:
                cv2.waitKey(50)

        return corners2.reshape((m, n, 2))
    else:
        print(filename, img.shape, "Failed")
        return None


def detect_all_chessboards(filenames, **kwargs):
    jobs = [joblib.delayed(detect_single_chessboard, check_pickle=False)(name, plot=False, **kwargs) for name in filenames]

    results = joblib.Parallel(verbose=15, n_jobs=-1, batch_size=1, pre_dispatch="all")(jobs)
    results = {name: result for name, result in zip(filenames, results) if result is not None}

    return results


def paint_corners(path, plot=False):
    with open(path + "/corners.json", "r") as f:
        corners = json.load(f)

    for i, (name, results) in enumerate(corners.items()):
        img = cv2.imread(name)
        results = np.array(results).reshape(-1, 2)
        img = cv2.drawChessboardCorners(img, (N, M), results[:, None, :].astype(np.float32), True)
        cv2.imwrite(name[:-4] + "_painted.jpg", img)
        # break
        if plot:
            cv2.imshow('img', img)
            while cv2.getWindowProperty('img', 0) >= 0:
                cv2.waitKey(50)


def reprojection_errors(objpoints, imgpoints, calibration):
    ret, mtx, dist, rvecs, tvecs = calibration

    errors = []
    for i, (objpt, imgpt) in enumerate(zip(objpoints, imgpoints)):
        imgpoints2, _ = cv2.projectPoints(objpt, rvecs[i], tvecs[i], mtx, dist)
        imgpoints2 = imgpoints2.reshape((objpt.shape[0], 2))
        # errors.append(cv2.norm(imgpt, imgpoints2, cv2.NORM_L2) / len(imgpoints2))
        errors.append(np.average(np.linalg.norm(imgpt - imgpoints2, axis=1)))

    return np.array(errors)


def calibrate(filename, dir, title, example=1000, plot=True):
    # Uncomment this section to extract frames from video
    # extract_images(filename, dir, step=5)
    # return

    filenames = sorted(glob.glob(dir + '/*.jpg'))
    print(len(filenames), "images")

    # Test chessboard detector
    # detect_single_chessboard(filenames[100], resize=False)
    # return

    # Uncomment this section to detect chessboards and corners. Cached results are used otherwise
    # corners = detect_all_chessboards(filenames, resize=False)
    #
    # with open(dir + "/corners.json", "w") as f:
    #     json.dump({n: c.tolist() for n, c in corners.items()}, f, indent=4)
    # return

    with open(dir + "/corners.json", "r") as f:
        corners = json.load(f)

    print("\n%d detected" % len(corners))
    corners2 = {}

    def order(item):
        key = item[0]
        return int(os.path.basename(key)[:-4])

    for i, (name, results) in enumerate(sorted(corners.items(), key=order)):
        if i % 2 == 0 and i > 50 and i < 150:
            # print(name)
            corners2[name] = results
    corners = corners2
    print("\n%d in use" % len(corners))

    # 20 mm checker size
    objp = np.zeros((N * M, 3), np.float32)
    objp[:, :2] = np.mgrid[0:N, 0:M].T.reshape(-1, 2)*20

    objpoints = [objp] * len(corners)
    imgpoints = []
    names = []

    for name, results in corners.items():
        imgpoints.append(np.array(results).reshape((N*M, 2)).astype(np.float32))
        names.append(name)

    # Pick image to be undistorted as an example
    img = cv2.imread(dir + "/%d.jpg" % example)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Uncomment this section to compute full calibration. Cached results are used otherwise
    # flags = cv2.CALIB_FIX_K1 | cv2.CALIB_FIX_K2 | cv2.CALIB_FIX_K3 | cv2.CALIB_FIX_TANGENT_DIST
    # full_calibration = cv2.calibrateCamera(objpoints, imgpoints, gray.shape[::-1], None, None, flags=flags)
    # with open(dir + "/full_calibration.pkl", "wb") as f:
    #     pickle.dump(full_calibration, f)
    # return

    with open(dir + "/full_calibration.pkl", "rb") as f:
        full_calibration = pickle.load(f)

    errors = reprojection_errors(objpoints, imgpoints, full_calibration)
    # print(errors, "\nmean error:", np.mean(errors))
    print("mean error:", np.mean(errors))

    # thr = np.mean(errors)
    thr = 1.5

    idx = np.nonzero(np.array(errors) < thr)[0]
    print("\n%d selected" % idx.shape[0])

    objpoints2 = [objpoints[i] for i in idx]
    imgpoints2 = [imgpoints[i] for i in idx]

    # Uncomment this section to compute refined calibration. Cached results are used otherwise
    # flags = cv2.CALIB_FIX_K1 | cv2.CALIB_FIX_K2 | cv2.CALIB_FIX_K3 | cv2.CALIB_FIX_TANGENT_DIST
    # refined_calibration = cv2.calibrateCamera(objpoints2, imgpoints2, gray.shape[::-1], None, None, flags=flags)
    # with open(dir + "/refined_calibration.pkl", "wb") as f:
    #     pickle.dump(refined_calibration, f)
    # with open(dir + title, "w") as f:
    #     mtx = refined_calibration[1]
    #     err = reprojection_errors(objpoints2, imgpoints2, refined_calibration)
    #     json.dump({"mtx": mtx.tolist(),
    #                "scale_x": float(mtx[0, 0]),
    #                "scale_y": float(mtx[1, 1]),
    #                "center_col": float(mtx[0, 2]),
    #                "center_row": float(mtx[1, 2]),
    #                "origin": "top-left",
    #                "projection_error, pix": float(np.mean(err))}, f, indent=4)
    # return

    with open(dir + "/refined_calibration.pkl", "rb") as f:
        refined_calibration = pickle.load(f)

    errors2 = reprojection_errors(objpoints2, imgpoints2, refined_calibration)
    # print(errors2, "\nmean error 2:", np.mean(errors2))
    print("mean error 2:", np.mean(errors2))

    ret, mtx, dist, rvecs, tvecs = refined_calibration
    print("\nmtx", mtx)
    print("\ndist", dist)

    if plot:
        plt.figure(filename + " - Errors", (12, 9))
        plt.plot(np.arange(errors.shape[0]), errors, ".r", label="All")
        plt.plot(idx, errors2, ".b", label="Refined")
        plt.plot([0, errors.shape[0]], [thr, thr], '--k', label="Threshold")
        plt.title("Camera Calibration Reprojection Errors")
        plt.xlabel("Image #")
        plt.ylabel("Error, pixels")
        plt.ylim([0, 1.1*np.max(errors)])
        plt.legend()
        plt.tight_layout()
        plt.savefig(dir + "/errors.png", dpi=160)

    h, w = img.shape[:2]
    new_mtx, roi = cv2.getOptimalNewCameraMatrix(mtx, dist, (w, h), 1, (w, h))
    print("\nnew_mtx", new_mtx)

    dst = cv2.undistort(img, mtx, dist, None, new_mtx)
    mapx, mapy = cv2.initUndistortRectifyMap(mtx, dist, None, new_mtx, (w, h), 5)
    dst = cv2.remap(img, mapx, mapy, cv2.INTER_LINEAR)

    # Uncomment this this section to crop black edges after remapping
    # x, y, w, h = roi
    # dst = dst[y:y + h, x:x + w]

    cv2.imwrite(dir + '/original.png', img)
    cv2.imwrite(dir + '/undistorted.png', dst)

    if plot:
        plt.figure(filename + " - Undistorted", (12, 9))
        plt.imshow(dst)
        plt.plot(mtx[0,2], mtx[1,2], ".r")
        plt.plot(new_mtx[0,2], new_mtx[1,2], ".b")


if __name__ == "__main__":
    base_filename = "/home/yurii/data/reip_%d/camera_calibration/%s/calib_coarse.avi"
    base_dir = "/home/yurii/data/reip_%d/camera_calibration/%s/calib_coarse/"

    # base_filename = "/home/yurii/data/reip_%d/camera_calibration/%s/calib_fine.avi"
    # base_dir = "/home/yurii/data/reip_%d/camera_calibration/%s/calib_fine/"

    # detect_single_chessboard(base_dir % (1, "right") + "1000.jpg", plot=False)
    # paint_corners(base_dir % (1, "right"), plot=False)

    # i, side = 5, "right"
    # calibrate(base_filename % (i, side), base_dir % (i, side), side, example=1000, plot=True)

    for i in range(6):
        for side in ["left", "right"]:
            print("\n", i + 1, side)
            calibrate(base_filename % (i+1, side), base_dir % (i+1, side), side + "_%d.json" % (i+1), example=1000, plot=True)

    plt.show()
