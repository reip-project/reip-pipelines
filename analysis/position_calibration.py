import cv2
import json
import numpy as np
from cv2 import aruco
import matplotlib.pyplot as plt


def extract_frame(vid_name, frame, frame_name):
    vid = cv2.VideoCapture(vid_name)
    vid.set(cv2.CAP_PROP_POS_FRAMES, frame)
    ret, frame = vid.read()
    if ret:
        cv2.imwrite(frame_name, frame)
    else:
        print("Failed reading frame %d in %s" % (frame, vid_name))


def axis_equal_3d(ax):
    extents = np.array([getattr(ax, 'get_{}lim'.format(dim))() for dim in 'xyz'])
    sz = extents[:,1] - extents[:,0]
    centers = np.mean(extents, axis=1)
    maxsize = max(abs(sz))
    r = maxsize/2
    for ctr, dim in zip(centers, 'xyz'):
        R = r * 3 / 4 if dim == 'z' else r
        getattr(ax, 'set_{}lim'.format(dim))(ctr - R, ctr + R)


def line(ax, p1, p2, *args, **kwargs):
    ax.plot([p1[0], p2[0]], [p1[2], p2[2]], [-p1[1], -p2[1]], *args, **kwargs)


def basis(ax, T, R, *args, length=1, **kwargs):
    line(ax, T, T + length * R[:, 0], "r")
    line(ax, T, T + length * R[:, 1], "g")
    line(ax, T, T + length * R[:, 2], "b")


def board(ax, T, R, *args, label="", **kwargs):
    line(ax, T, T + 375 * R[:, 0], "orange", linestyle="--", label=label)
    line(ax, T, T + 270 * R[:, 1], "orange", linestyle="--")
    line(ax, T + 375 * R[:, 0], T + 375 * R[:, 0] + 270 * R[:, 1], "orange", linestyle="--")
    line(ax, T + 270 * R[:, 1], T + 375 * R[:, 0] + 270 * R[:, 1], "orange", linestyle="--")

    basis(ax, T, R, length=15)


def sensor(ax, *args, width=146, height=222, depth=56, up=12, behind=13, radius=54, from_top=74, **kwargs):
    ex, ey, ez = np.array([width/2, 0, 0]), np.array([0, height/2, 0]), np.array([0, 0, depth/2])
    o = np.array([0, -up, -behind]) - ey -ez
    v = [(i, j, k) for i in [-1, 1] for j in [-1, 1] for k in [-1, 1]]
    for i, j in [(0, 1), (1, 3), (3, 2), (2, 0), (4, 5), (5, 7), (7, 6), (6, 4), (0, 4), (1, 5), (2, 6), (3, 7)]:
        line(ax, o + v[i][0]*ex + v[i][1]*ey + v[i][2]*ez, o + v[j][0]*ex + v[j][1]*ey + v[j][2]*ez, *args, **kwargs)
    o, n = o - ey + [0, from_top, 0] + ez, 36
    ex, ey = np.array([radius, 0, 0]), np.array([0, radius, 0])
    for i in range(n):
        line(ax, o + ex * np.sin(i * 2 * np.pi / n) + ey * np.cos(i * 2 * np.pi / n),
             o + ex * np.sin((i+1) * 2 * np.pi / n) + ey * np.cos((i+1) * 2 * np.pi / n),
             *args, label="Sensor outline" if i == 0 else None, **kwargs)


# resize - for display only
def detect_charuco(img, resize=4, plot=False, save=None, roi=None):
    aruco_dict = aruco.Dictionary_get(aruco.DICT_5X5_250)
    board = aruco.CharucoBoard_create(25, 18, 15, 15 * 7 / 9, aruco_dict)

    m_pos, m_ids, _ = cv2.aruco.detectMarkers(img, aruco_dict)

    if len(m_pos) > 0:
        count, c_pos, c_ids = cv2.aruco.interpolateCornersCharuco(m_pos, m_ids, img, board)

        if plot or save:
            img2 = cv2.resize(img, (img.shape[1] // resize, img.shape[0] // resize))
            img2 = aruco.drawDetectedMarkers(np.repeat(img2[:, :, None], 3, axis=2), np.array(m_pos) / resize, m_ids)
            img2 = aruco.drawDetectedCornersCharuco(img2, np.array(c_pos) / resize, c_ids, cornerColor=(0, 255, 0))

            if save:
                roi = roi // resize if roi is not None else None
                cv2.imwrite(save, img2[roi[1]:roi[3], roi[0]:roi[2], :] if roi is not None else img2)

            if plot:
                cv2.imshow('img', img2)
                while cv2.getWindowProperty('img', 1) >= 0:
                    cv2.waitKey(50)

        return board.chessboardCorners[c_ids].reshape((-1, 3)), np.array(c_pos).reshape((-1, 2))
    else:
        return None


if __name__ == "__main__":
    base_filename = "/home/yurii/data/reip_%d/camera_calibration/position_%s.avi"
    base_dir = "/home/yurii/data/reip_%d/camera_calibration/"

    # microphone array dimensions
    x_stride, y_stride = 93, 72  # mm
    mic_y, mic_x = np.meshgrid(np.arange(3), np.arange(4), indexing="ij")
    mic_x, mic_y = (mic_x - 1.5) * x_stride, (mic_y - 1) * y_stride

    # charuco board origin (bottom-left) offset with respect to the microphone array (center)
    # with coordinate system like for camera (x - right, y - down, z - forward)
    x_offset, y_offset, z_offset = -375 / 2, 92, 324  # mm
    T0 = np.array([x_offset, y_offset, z_offset])
    R0 = np.array([[1, 0, 0],
                   [0, -1, 0],
                   [0, 0, -1]])

    for i in range(6):
        plt.figure(str(i+1), (14, 12))
        ax = plt.subplot(111, projection='3d', proj_type='ortho')
        ax.set_title("Positions %d" % (i+1))
        ax.plot(mic_x.ravel(), np.zeros(12), -mic_y.ravel(), "go", label="Microphones")
        sensor(ax, "k--")
        board(ax, T0, R0, label="Calibration board")

        pos = {"definitions" : "https://docs.opencv.org/2.4/modules/calib3d/doc/camera_calibration_and_3d_reconstruction.html"}
        pos["array"] = {}
        pos["array"]["x_stride"] = 93
        pos["array"]["y_stride"] = 72
        pos["array"]["num_x"] = 4
        pos["array"]["num_y"] = 3
        pos["array"]["origin"] = "center"
        pos["array"]["axis"] = "x - right, y - down, z - forward"

        for side in ["left", "right"]:
            pos[side] = {}
            print("\n", i + 1, side)
            frame_name = base_dir % (i+1) + side + ".jpg"

            # extract_frame(base_filename % (i+1, side), 5 * 15, frame_name)

            gray = cv2.cvtColor(cv2.imread(frame_name), cv2.COLOR_BGR2GRAY)
            obj, img = detect_charuco(gray, resize=1, plot=False)
            print(obj.shape, img.shape)

            with open("calibration_data/%s_%d.json" % (side, i+1), "r") as f:
                calib = json.load(f)
                mtx = np.array(calib["mtx"])
                # print("mtx:\n", mtx)

            ax.plot(obj[:, 0] + x_offset, np.ones_like(obj[:, 0]) * z_offset, obj[:, 1] - y_offset,
                    "r+" if side == "left" else "bx", label="Corners (%s)" % side)

            ret, rvec, tvec = cv2.solvePnP(obj, img, mtx, None)
            T, (R, _) = tvec.ravel(), cv2.Rodrigues(rvec)
            # board(ax, T, R, label="Intermediate (%s)" % side)
            # print("\nT:", T)
            # print("R:\n", R)

            CT = T0 + np.matmul(R0, np.matmul(R.T, -T))
            CR = np.matmul(R0, R.T)
            print("\nCamera T:", CT)
            print("Camera R:\n", CR)

            pos[side]["cam_T"] = CT.tolist()
            pos[side]["cam_R"] = CR.T.tolist()
            pos[side]["T_units"] = "mm"
            pos[side]["R_help"] = "[[ex], [ey], [ez]]"

            basis(ax, CT, CR, length=20)

        with open("calibration_data/positions_%d.json" % (i+1), "w") as f:
            json.dump(pos, f, indent=4)

        ax.set_xlabel("x, mm")
        ax.set_ylabel("z, mm")
        ax.set_zlabel("-y, mm")
        plt.legend()
        plt.tight_layout()
        axis_equal_3d(ax)
        ax.view_init(elev=20, azim=-35)
        plt.savefig(base_dir % (i+1) + "positions.png", dpi=200)
        plt.savefig("calibration_data/positions_%d.png" % (i+1), dpi=200)

    plt.show()
