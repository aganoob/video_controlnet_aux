import gradio as gr

from controlnet_aux.processor import Processor

# Add any necessary module names that should not be imported with wildcard import above.

import os
import cv2
from PIL import Image
from moviepy.editor import *
import argparse
import re

HF_MODEL_NAME = "lllyasviel/Annotators"
DWPOSE_MODEL_NAME = "yzd-v/DWPose"
ANIFACESEG_MODEL_NAME = "bdsqlsz/qinglong_controlnet-lllite"
DENSEPOSE_MODEL_NAME = "LayerNorm/DensePose-TorchScript-with-hint-image"


def main(
    input_path="./",
    output_path="./",
):
    def initDetector(preprocesser_model):
        global processor
        processor = None
        processor = Processor(preprocesser_model)

    def regex(string):
        return re.findall(r"\d+", str(string))[-1]

    def get_frames(video_in):
        frames = []
        # resize the video
        clip = VideoFileClip(video_in)

        # check fps
        video_path = os.path.join(output_path, "video_resized.mp4")
        if clip.fps > 30:
            print("vide rate is over 30, resetting to 30")
            clip_resized = clip.resize(height=512)
            clip_resized.write_videofile(video_path, fps=30)
        else:
            print("video rate is OK")
            clip_resized = clip.resize(height=512)
            clip_resized.write_videofile(video_path, fps=clip.fps)

        print("video resized to 512 height")

        audioclip = clip_resized.audio

        # Opens the Video file with CV2
        cap = cv2.VideoCapture(video_path)

        fps = cap.get(cv2.CAP_PROP_FPS)
        print("video fps: " + str(fps))
        i = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if ret == False:
                break
            path = os.path.join(output_path, "raw" + str(i) + ".jpg")
            cv2.imwrite(path, frame)
            frames.append(path)
            i += 1

        cap.release()
        cv2.destroyAllWindows()
        print("broke the video into frames")

        return frames, fps, audioclip

    def get_openpose_filter(i, preprocesser_model):
        image = Image.open(i)

        # image = np.array(image)

        image = processor(image)
        # image = Image.fromarray(image)
        path = os.path.join(
            output_path, preprocesser_model + "_frame_" + regex(i) + ".jpeg"
        )
        image.save(path)
        return path

    def create_video(frames, fps, type, audioclip=None, scale=1.3):
        print("building video result")
        clip = ImageSequenceClip(frames, fps=fps)
        if audioclip:
            clip = clip.set_audio(audioclip)
        path = os.path.join(output_path, type + "_result.mp4")

        # squarify
        print("Squarifying...")
        clip = squarify_video_zoom_crop(clip, scale=scale)

        clip.write_videofile(path, fps=fps)

        return path

    def squarify_video_paddings(clip):
        # simply add paddings on the sides of the vertical clip

        # Calculate padding size
        width, height = clip.size
        padding_width = (height - width) // 2

        # Create padding clips
        padding_color = tuple(map(lambda x: int(x * 255), (0.267, 0.005, 0.329)))  # Viridis colormap zero
        left_padding = ColorClip(size=(padding_width, height), color=padding_color, duration=clip.duration)
        right_padding = ColorClip(size=(padding_width, height), color=padding_color, duration=clip.duration)

        # Create a square video with specific color paddings
        final_clip = CompositeVideoClip([left_padding.set_position((0,0)),
                                        clip.set_position((padding_width,0)),
                                        right_padding.set_position((width + padding_width,0))],
                                        size=(height, height))

        # Export the video
        return final_clip

    def squarify_video_zoom_crop(clip, scale=1.3, resize_to=(512, 512)):
        # add paddings on the sides of the vertical clip
        # and apply zooming in

        final_clip = squarify_video_paddings(clip)

        # Calculate current size
        width, height = final_clip.size

        # Scale up
        final_clip = final_clip.resize(scale)

        # Calculate new center
        w_new, h_new = final_clip.size
        x_center, y_center = w_new // 2, h_new // 2

        # Crop by the original size
        final_clip = final_clip.crop(
            x_center=x_center,
            y_center=y_center,
            width=width,
            height=height
        )
        final_clip = final_clip.resize(newsize=resize_to)

        # Export the video
        return final_clip

    def convertG2V(imported_gif):
        clip = VideoFileClip(imported_gif.name)
        path = os.path.join(output_path, "gif_video.mp4")
        clip.write_videofile(path)
        return path

    def infer(video_in, scale=1.3, preprocesser_model="densepose"):
        initDetector(preprocesser_model)
        # 1. break video into frames and get FPS
        frames_list, fps, audioclip = get_frames(video_in)

        # n_frame = int(trim_value*fps)
        n_frame = len(frames_list)

        if n_frame >= len(frames_list):
            print("video is shorter than the cut value")
            n_frame = len(frames_list)

        # 2. prepare frames result arrays
        result_frames = []
        print("set stop frames to: " + str(n_frame))

        for i in frames_list[0 : int(n_frame)]:
            openpose_frame = get_openpose_filter(i, preprocesser_model)
            result_frames.append(openpose_frame)
            print("frame " + i + "/" + str(n_frame) + ": done;")

        final_vid = create_video(result_frames, fps, 
                                 preprocesser_model, audioclip=audioclip, scale=scale)

        files = [final_vid]

        return final_vid, files

    def update_radio(table_colomn_1, table_colomn_2):
        if table_colomn_1 == "Openpose":
            options = [
                "animal_openpose",
                "densepose",
                "densepose_normal",
                "dw_openpose",
                "dw_openpose_face",
                "dw_openpose_faceonly",
                "dw_openpose_full",
                "dw_openpose_hand",
                "mediapipe_face",
                "openpose",
                "openpose_face",
                "openpose_faceonly",
                "openpose_full",
            ]
            value = "densepose"
        elif table_colomn_1 == "Depth":
            options = [
                "depth_leres",
                "depth_leres++",
                "depth_midas",
                "depth_zoe",
                "normal_bae",
                "normal_midas",
            ]
            value = "depth_zoe"
        elif table_colomn_1 == "Segment":
            options = [
                "anime_face_segment",
                "oneformer_ade20k",
                "oneformer_coco",
                "sam",
                "uniformer_ufade20k",
            ]
            value = "uniformer_ufade20k"
        elif table_colomn_1 == "Blur":
            options = [
                "tile",
            ]
            value = "tile"
        elif table_colomn_1 == "Line":
            options = [
                "canny",
                "lineart_anime",
                "lineart_coarse",
                "lineart_realistic",
                "mlsd",
                "scribble",
                "scribble_hed",
                "scribble_hedsafe",
                "scribble_pidinet",
                "scribble_pidsafe",
                "scribble_xdog",
                "softedge_hed",
                "softedge_hedsafe",
                "softedge_pidinet",
                "softedge_pidsafe",
            ]
            value = "lineart_realistic"
        elif table_colomn_1 == "Recolor":
            options = [
                "binary",
            ]
            value = "binary"
        else:
            options = [
                "animal_openpose",
                "densepose",
                "densepose_normal",
                "dw_openpose",
                "dw_openpose_face",
                "dw_openpose_faceonly",
                "dw_openpose_full",
                "dw_openpose_hand",
                "mediapipe_face",
                "openpose",
                "openpose_face",
                "openpose_faceonly",
                "openpose_full",
                "depth_leres",
                "depth_leres++",
                "depth_midas",
                "depth_zoe",
                "normal_bae",
                "normal_midas",
                "anime_face_segment",
                "oneformer_ade20k",
                "oneformer_coco",
                "sam",
                "uniformer_ufade20k",
                "tile",
                "binary",
                "canny",
                "lineart_anime",
                "lineart_coarse",
                "lineart_realistic",
                "mlsd",
                "scribble",
                "scribble_hed",
                "scribble_hedsafe",
                "scribble_pidinet",
                "scribble_pidsafe",
                "scribble_xdog",
                "softedge_hed",
                "softedge_hedsafe",
                "softedge_pidinet",
                "softedge_pidsafe",
            ]
            value = "densepose"
        table_colomn_2 = gr.Dropdown(
            choices=options,
            value=value,
            type="value",
            interactive=True,
        )
        return table_colomn_2

    title = """
<div style="text-align: center; max-width: 500px; margin: 0 auto;">
        <div
        style="
            display: inline-flex;
            align-items: center;
            gap: 0.8rem;
            font-size: 1.75rem;
            margin-bottom: 10px;
        "
        >
        <h1 style="font-weight: 600; margin-bottom: 7px;">
            Video_controlnet_aux
        </h1>
        </div>
    </div>
"""

    with gr.Blocks() as demo:
        with gr.Column():
            gr.HTML(title)
            with gr.Row():
                with gr.Column():
                    video_input = gr.Video(
                        value=None,
                    )
                    scale_input = gr.Number(
                        value=1.3,
                        label="Scale (zoom-in) Factor",
                        minimum=0.1,
                        maximum=2.,
                        step=0.1
                    )
                    submit_btn = gr.Button("Submit")

                with gr.Column():
                    video_output = gr.Video()
                    file_output = gr.Files()

        submit_btn.click(
            fn=infer,
            inputs=[video_input, scale_input],
            outputs=[video_output, file_output],
        )

    demo.launch(share=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i", "--input_path", type=str
    )
    parser.add_argument("-o", "--output_path", type=str, default="./outputs/")
    args = parser.parse_args()

    if not os.path.exists(args.output_path):
        os.makedirs(args.output_path)

    main(args.input_path, args.output_path)
