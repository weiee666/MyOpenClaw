import os  # 导入 os 处理环境变量
import sys  # 导入 sys 读取命令行参数

from openai import OpenAI  # 导入 OpenAI SDK


def main() -> None:  # 定义主函数
    api_key = os.getenv("OPENAI_API_KEY")  # 读取 API Key
    if not api_key:  # 判断是否缺少 Key
        raise SystemExit("Missing OPENAI_API_KEY environment variable.")  # 抛出错误提示

    try:  # 尝试解析数量参数
        target_count = int(sys.argv[1]) if len(sys.argv) > 1 else 8  # 读取目标数量
    except ValueError:  # 处理非法输入
        raise SystemExit(
            "Usage: python rag_websearch_slaythespire2.py [count]"
        )  # 返回用法提示

    client = OpenAI(api_key=api_key)  # 创建 OpenAI 客户端

    system_prompt = (
        "Return exactly the requested number of unique results. "
        "Output JSON only, no extra text. Each item: title, url, summary."
    )  # 设定系统提示
    user_prompt = (
        f'Search for {target_count} results about "杀戮尖塔2攻略". '
        "Prefer recent, detailed strategy guides or walkthroughs."
    )  # 设定用户提示

    response = client.responses.create(  # 调用 Responses API
        model="gpt-5.4",  # 指定模型
        input=[
            {"role": "system", "content": system_prompt},  # 注入系统提示
            {"role": "user", "content": user_prompt},  # 注入用户提示
        ],
        tool_choice={"type": "web_search"},  # 强制使用 web_search 工具
        tools=[{"type": "web_search"}],  # 注册 web_search 工具
        reasoning={"effort": "none"},  # 关闭额外推理输出
        text={"verbosity": "low"},  # 控制文本冗余
    )  # 发起请求

    print(response.output_text)  # 输出结果


if __name__ == "__main__":  # 脚本入口
    main()  # 执行主函数
