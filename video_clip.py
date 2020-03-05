import tkinter as tk
from math import floor
import os

window = tk.Tk()
try:
    import numpy as np
    import sounddevice as sd
    from moviepy.editor import VideoFileClip, concatenate_videoclips  # 本行必须在 tk.Tk()之后，不然会出错
except Exception as e:
    print('\n正在安装需要的工具包，若出错很可能是网络访问问题，确认网络连接后重新运行即可 ... ... ...\n')
    o = os.popen('pip install numpy')
    print(o.read())
    o = os.popen('pip install sounddevice')
    print(o.read())
    o = os.popen('pip install moviepy')
    print(o.read())
    print('\n工具包安装完成，若运行出错重新运行即可！\n')

    import numpy as np
    import sounddevice as sd
    from moviepy.editor import VideoFileClip, concatenate_videoclips  # 本行必须在 tk.Tk()之后，不然会出错


def main(window):

    window_width = 1200
    window_height = 300
    unit_width = 0.3
    sample_step = 50

    video_file = input('请输入视频路戏或文件名（当前路径），支持的视频格式有 .ogv、.mp4、.mpeg、.avi、.mov：')
    if video_file == '':
        video_file = "./video.mov"
    print("正在读入、处理视频文件，请耐心等待 ... ...")
    # 使用moviepy加载视频中的音频
    sample_rate = 44100
    video = VideoFileClip(video_file)
    sound = video.audio.to_soundarray(fps=sample_rate)
    audio = sound[:, 0]

    window.title("[标注：Space] | [取消标注：BackSpace] | [下一页：F、Return、或Down] | 上一页：B或Up] | [保存标注：S，输出labels.npy] | [导出视频：Ctrl+O，输出output.mp4]")
    audio_keeper = AudioKeeper(audio, sample_step, page_size=window_width/unit_width, audio_sample_rate=sample_rate)
    canvas = AudioBox(window, width=window_width, height=window_height, unit_width=unit_width,
                      audio_keeper=audio_keeper, video=video)
    canvas.pack()
    canvas.draw_lines()
    canvas.bind_events()
    window.bind('<FocusIn>', lambda e: canvas.focus_set())
    window.mainloop()


class AudioBox(tk.Canvas):  # pylint: disable=too-many-ancestors
    def __init__(self, root, width, height, unit_width, audio_keeper, video):
        super().__init__(root, width=width, height=height)
        self.unit_width = unit_width
        self.box_width = width
        self.box_height = height
        self.audio_keeper = audio_keeper
        self.audio_keeper.next_page()
        self.video = video

        # 鼠标拖出的矩形
        self.drag_start_x = None   # 会被置None
        self.drag_start_x_ = None  # 不会被置None
        self.drag_end_x = None
        self.drag_up_y = self.box_height * 0.5 + self.box_height * 0.5 * 0.8
        self.drag_down_y = self.box_height * 0.5 - self.box_height * 0.5 * 0.8

        self.drag_shape = None

    def get_pos(self):
        start = int(self.drag_start_x_/self.unit_width)
        end = int(self.drag_end_x/self.unit_width)
        return start, end

    def on_drag(self, event):
        if self.drag_start_x is None:
            self.drag_start_x = event.x
            self.drag_start_x_ = event.x
        if event.x < 0:
            self.drag_end_x = 0
        elif event.x > self.box_width:
            self.drag_end_x = self.box_width
        else:
            self.drag_end_x = event.x

        if self.drag_shape is not None:
            self.delete(self.drag_shape)
            self.drag_shape = None
        self.drag_shape = self.create_rectangle(self.drag_start_x, self.drag_up_y,
                                                self.drag_end_x, self.drag_down_y, outline='red')

    def on_drag_end(self, event):  # pylint: disable=unused-argument
        self.drag_start_x = None
        if self.drag_start_x_ is None:
            return
        start, end = self.get_pos()
        self.audio_keeper.play(start, end)

    def on_space(self, event):  # pylint: disable=unused-argument
        self.do_label(True)

    def on_backspace(self, event):  # pylint: disable=unused-argument
        self.do_label(False)

    def do_label(self, do):
        if self.drag_shape is None:
            return

        start, end = self.get_pos()
        if do:
            self.audio_keeper.do_label(start, end, 1)
            self.create_line(self.drag_start_x_, self.box_height-10, self.drag_end_x,
                             self.box_height-10, fill='red', width=10)
        else:
            self.audio_keeper.do_label(start, end, 0)
            self.create_line(self.drag_start_x_, self.box_height-10, self.drag_end_x,
                             self.box_height-10, fill='white', width=10)

    def on_page_down(self, event):  # pylint: disable=unused-argument
        if self.audio_keeper.next_page():
            self.delete('all')
            self.draw_lines()

    def on_page_up(self, event):  # pylint: disable=unused-argument
        if self.audio_keeper.prev_page():
            self.delete('all')
            self.draw_lines()

    def on_key(self, event):
        if event.char == 'f':
            self.on_page_down(event)  # 下页
        elif event.char == 'b':
            self.on_page_up(event)    # 上页
        elif event.char == 's':
            self.audio_keeper.save_label()  # 保存标签

    def draw_lines(self):
        audio_samples = self.audio_keeper.page_sample
        lines = [make_line(y1, y2, i, self.unit_width, self.box_height) for i, (y1, y2)
                 in enumerate(zip(audio_samples[:-1], audio_samples[1:]))]

        # 画音频
        for line in lines:
            self.create_line(*line, fill='blue')

        # 画标签
        for line in make_label_lines(self.audio_keeper.page_label_sample, self.unit_width, self.box_height):
            self.create_line(line, fill='red', width=10)

    def on_clip(self, event):  # pylint: disable=unused-argument
        """根据标签切分视频"""
        print('视频剪切中... ...')
        clip_video(self.video, self.audio_keeper.labels, './output.mp4', self.audio_keeper.audio_sample_rate)
        print('视频剪切成功！输出文件为 output.mp4')
        tmp_file = './outputTEMP_MPY_wvf_snd.mp3'
        if os.path.exists(tmp_file):
            os.remove(tmp_file)

    def bind_events(self):
        self.focus_set()
        self.bind('<Button-1>', lambda e: self.focus_set())
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonRelease-1>", self.on_drag_end)
        self.bind('<space>', self.on_space)
        self.bind('<BackSpace>', self.on_backspace)
        self.bind('<Return>', self.on_page_down)
        self.bind('<Down>', self.on_page_down)
        self.bind('<Up>', self.on_page_up)
        self.bind('<Key>', self.on_key)
        self.bind('<Control-o>', self.on_clip)


class AudioKeeper:
    def __init__(self, audio, sample_step, page_size, audio_sample_rate):
        self.audio = audio
        self.sample_step = sample_step
        self.labels = np.array([0] * len(audio))
        self.page_overlap = 5000
        self.page_size = int(page_size * sample_step - self.page_overlap)
        self.audio_sample_rate = audio_sample_rate

        self.label_times = 0

        self.page_id = -1
        self.page_start = 0
        self.page_end = 0
        self.page_sample = None

        self.max_page = floor(len(audio) / self.page_size)
        print('Max Page:', self.max_page)

    def real_pos(self, start, end):
        """窗口位置转为列表位置 """
        page_start = (self.page_id) * self.page_size
        start = start * self.sample_step + page_start
        end = end * self.sample_step + page_start
        return min(start, end), max(start, end)

    def play(self, start, end):
        """播放选中音频"""
        start, end = self.real_pos(start, end)
        sd.play(self.audio[start:end], self.audio_sample_rate)

    def do_label(self, start, end, label_value):
        start, end = self.real_pos(start, end)
        self.labels[start:end] = label_value
        self.label_times += 1
        if self.label_times % 20 == 0:  # 每20个标注保存一次
            self.save_label()

    def save_label(self):
        np.save('labels.npy', self.labels)
        print('标签保存成功！')

    def create_page(self):
        """构建当前页数据"""
        self.page_start = self.page_id * self.page_size
        self.page_end = (self.page_id + 1) * self.page_size + self.page_overlap
        self.page_sample = self.audio[self.page_start:self.page_end:self.sample_step]
        self.page_label_sample = self.labels[self.page_start:self.page_end:self.sample_step]

    def next_page(self):
        """前一页"""
        if self.page_id == self.max_page:
            return False
        self.page_id += 1
        self.create_page()
        print(f'页码：{self.page_id}/{self.max_page}')
        return True

    def prev_page(self):
        """后一页
        """
        if self.page_id == 0:
            return False
        self.page_id -= 1
        self.create_page()
        print(f'页码：{self.page_id}/{self.max_page}')
        return True


def make_line(n1, n2, pos, unit_width, box_height):
    """创建一个音频线段"""
    x1 = pos * unit_width
    x2 = (pos + 1) * unit_width
    y1 = n1 * box_height + 0.5 * box_height
    y2 = n2 * box_height + 0.5 * box_height
    return x1, y1, x2, y2


def make_label_lines(label_sample, unit_width, box_height):
    """创建所有标签线段"""
    # label_sample = self.audio_keeper.page_label_sample
    seg_points = np.nonzero(label_sample[:-1] != label_sample[1:])[0]
    seg_points += 1
    if label_sample[0] == 1:
        seg_points = np.insert(seg_points, 0, 0)
    if label_sample[-1] == 1:
        seg_points = np.append(seg_points, len(label_sample)-1)
    starts = seg_points[::2]
    ends = seg_points[1::2]
    labels_segs = zip(starts, ends)
    labels_lines = []
    for s, e in labels_segs:
        labels_lines.append((s * unit_width, box_height-10,
                             e * unit_width, box_height-10))
    return labels_lines


def clip_video(video, labels, out_file='output.mp4', sample_rate=44100):
    """根据标签剪切视频"""
    # 查找片段
    seg_points = np.nonzero(labels[:-1] != labels[1:])[0]
    seg_points += 1
    if labels[0] == 0:
        seg_points = np.insert(seg_points, 0, 0)
    if labels[-1] == 0:
        seg_points = np.append(seg_points, len(labels)-1)
    starts = seg_points[::2]
    ends = seg_points[1::2]

    # 根据片段提取视频
    videos = []

    # videos.append(video.subclip(0, first_end/sample_rate))
    for i, (start, end) in enumerate(zip(starts, ends)):
        print(f'片段 {i}/{len(starts)}')
        videos.append(video.subclip(start/sample_rate, end/sample_rate))

    # 合并视频
    cat_videos = concatenate_videoclips(videos)

    # 保存视频
    cat_videos.to_videofile(out_file, fps=24, remove_temp=False)


if __name__ == '__main__':
    main(window)
