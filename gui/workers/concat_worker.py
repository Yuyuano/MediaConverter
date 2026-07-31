from gui.workers.base import MediaWorker


class ConcatWorker(MediaWorker):

    def __init__(self, converter, input_files, output_file, stream_copy):
        super().__init__(converter)
        self.input_files = input_files
        self.output_file = output_file
        self.stream_copy = stream_copy

    def run(self):
        try:
            if not self.converter.ffmpeg_path:
                if not self.converter.init():
                    self.log.emit('error', 'FFmpeg 未找到或初始化失败')
                    self.finished.emit(False, '')
                    return

            self.converter.reset_cancellation()
            self._bridge_callbacks()
            success = self.converter.concat_videos(
                self.input_files, self.output_file, self.stream_copy
            )
            self.finished.emit(success, self.output_file if success else '')
        except Exception as e:
            import logging
            logging.getLogger('MediaConverter').error(f"拼接异常: {e}", exc_info=True)
            self.finished.emit(False, '')
        finally:
            self.converter.reset_callbacks()

    def cancel(self):
        self.converter.cleanup()
