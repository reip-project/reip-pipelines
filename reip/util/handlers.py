'''
Manage a list of functions/context managers as if they are one.
'''
import time
import reip


def lineprofile(block, run):
    try:
        import pyinstrument
        prof = pyinstrument.Profiler()
        prof.start()
        return run()
    finally:
        prof.stop()
        print(prof.output_text(unicode=True, color=True))


def reboot(block, run):
    while not block.closed:
        try:
            return run()
        except Exception as e:
            block.log.error(reip.util.excline(e))


def retry(n=None, sleep=None):
    def retry(block, run):
        for i in reip.util.iters.loop():
            try:
                return run()
            except Exception as e:
                if n and i == n-1:
                    raise
                block.log.error(reip.util.excline(e))
                if sleep:
                    time.sleep(sleep)
            else:
                break
    return retry


def suppress(block, run):
    try:
        return run()
    except Exception:
        pass


def heartrate(block, run):
    import heartrate
    heartrate.trace(browser=True)
    return run()
