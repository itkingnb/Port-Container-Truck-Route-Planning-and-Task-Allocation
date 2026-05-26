import matplotlib.pyplot as plt
import argparse
import sys

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False


def run_matplotlib_mode(args):
    from simulation import PortSimApp

    app = PortSimApp(
        num_trucks=args.trucks,
        port_cols=args.cols,
        port_rows=args.rows,
        use_ml_predictor=not args.no_ml,
        use_congestion_prediction=not args.no_congestion,
        headless=False
    )
    app.run()


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
    parser = argparse.ArgumentParser(description="Port Container Truck Dispatch System")
    parser.add_argument("--mode", choices=["matplotlib", "web"], default="matplotlib",
                        help="Run mode: matplotlib window or web server")
    parser.add_argument("--trucks", type=int, default=4, help="Number of trucks")
    parser.add_argument("--cols", type=int, default=8, help="Port grid columns")
    parser.add_argument("--rows", type=int, default=3, help="Port grid rows")
    parser.add_argument("--no-ml", action="store_true", help="Disable ML task value prediction")
    parser.add_argument("--no-congestion", action="store_true",
                        help="Disable congestion prediction")
    parser.add_argument("--host", default="127.0.0.1", help="Web server host")
    parser.add_argument("--port", type=int, default=5000, help="Web server port")

    args = parser.parse_args()

    if args.mode == "web":
        print(f"Starting web server at http://{args.host}:{args.port}")
        print(f"Configuration: {args.trucks} trucks, {args.cols}x{args.rows} port grid")
        run_web_mode(args)
    else:
        print(f"Starting matplotlib mode with {args.trucks} trucks...")
        run_matplotlib_mode(args)
