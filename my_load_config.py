
import os
from dotenv import load_dotenv
load_dotenv("D:/codes/ydfhome/importtantdir/envs/sec_dotenv.env", override=True)



SILICONFLOW_API_KEY = os.environ["SILICONFLOW_API_KEY"]

os.environ["NBRAG_API_KEY"] = SILICONFLOW_API_KEY