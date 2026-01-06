import pandas as pd

def get_data_from_excel(file_path: str) -> str:
    # 支持xlsx和xls文件
    try:
        df = pd.read_excel(file_path)
        return df.to_markdown()
    except FileNotFoundError:
        print("错误：文件未找到。")
        return None
    except Exception as e:
        print(f"读取时发生错误: {e}")
        return None

