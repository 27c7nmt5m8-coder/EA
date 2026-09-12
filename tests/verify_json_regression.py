from pathlib import Path
import json_support as suite
suite.ROOT=Path(__file__).resolve().parents[1]/'src'
suite.TEST=Path(__file__).resolve().parents[1]/'verification'
suite.TEST.mkdir(exist_ok=True)
if __name__=='__main__':suite.verify()
