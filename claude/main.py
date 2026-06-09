import argparse
import sys


def run_web_mode(args):
    from web_server import run_server
    run_server(
        num_trucks=args.trucks,
        port_cols=args.cols,
        port_rows=args.rows,
        use_ml_predictor=not args.no_ml,
        use_congestion_prediction=not args.no_congestion,
        host=args.host,
        port=args.port
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="港口集卡路径规划与任务分配智能调度系统")
    parser.add_argument("--trucks", type=int, default=4, help="卡车数量")
    parser.add_argument("--cols", type=int, default=8, help="港口网格列数")
    parser.add_argument("--rows", type=int, default=3, help="港口网格行数")
    parser.add_argument("--no-ml", action="store_true", help="禁用ML任务价值预测")
    parser.add_argument("--no-congestion", action="store_true", help="禁用拥堵趋势预测")
    parser.add_argument("--host", default="127.0.0.1", help="Web服务器地址")
    parser.add_argument("--port", type=int, default=5000, help="Web服务器端口")

    args = parser.parse_args()

    print(f"启动Web服务器: http://{args.host}:{args.port}")
    print(f"配置: {args.trucks}辆卡车, {args.cols}×{args.rows} 港口网格")
    run_web_mode(args)
