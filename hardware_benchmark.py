import os
import sys
import time
import argparse

def restrict_hardware(cores: int):
    """
    Must be called BEFORE importing heavy scientific libraries.
    This forces the underlying C/C++ backends to limit their hardware threads,
    perfectly mimicking a CPU with a specific number of cores.
    """
    os.environ["OMP_NUM_THREADS"] = str(cores)
    os.environ["OPENBLAS_NUM_THREADS"] = str(cores)
    os.environ["MKL_NUM_THREADS"] = str(cores)
    os.environ["VECLIB_MAXIMUM_THREADS"] = str(cores)
    os.environ["NUMEXPR_NUM_THREADS"] = str(cores)

def main():
    parser = argparse.ArgumentParser(description="Simulate hardware constraints for UTI Screener")
    parser.add_argument("--cores", type=int, default=os.cpu_count(), help="Number of CPU cores to simulate")
    parser.add_argument("--iterations", type=int, default=10, help="Number of passes to average")
    args = parser.parse_args()

    # 1. Lock the hardware limits FIRST
    restrict_hardware(args.cores)

    # 2. Now import libraries and enforce limits on them
    import cv2
    import torch
    import psutil
    
    cv2.setNumThreads(args.cores)
    torch.set_num_threads(args.cores)
    
    # Force PyTorch to use CPU (mimicking a phone/chromebook without an M-series GPU)
    os.environ["CUDA_VISIBLE_DEVICES"] = "" 
    
    # Imports fixed to pull from the correct module
    from core.strip_analyzer import StripAnalyzer
    from core.calibration import CalibrationModel

    print("=" * 50)
    print(f"🔬 HARDWARE SIMULATOR: {args.cores} CPU CORE(S)")
    print(f"🔄 Iterations per test: {args.iterations}")
    print("=" * 50)

    # Load components
    print("[1/3] Loading model and instantiating analyzer...")
    model = CalibrationModel.load("models/model.json")

    analyzer = StripAnalyzer()
    img_path = "tests/samples/true_samples/top_level/Leu75Nit1.jpg"
    config_path = "config/strip_config.json"  # Required by your analyze() function

    # Warmup pass (forces YOLO/PyTorch to initialize memory graphs so we don't measure startup time)
    print("[2/3] Warming up the pipeline...")
    _ = analyzer.analyze(img_path, model, config_path, pre_cropped=False)

    print("[3/3] Running benchmark...")
    start_time = time.perf_counter()

    for i in range(args.iterations):
        _ = analyzer.analyze(img_path, model, config_path, pre_cropped=False)
        sys.stdout.write(f"\r  Processed {i+1}/{args.iterations}")
        sys.stdout.flush()

    end_time = time.perf_counter()

    total_time = end_time - start_time
    time_per_image = total_time / args.iterations
    fps = 1.0 / time_per_image

    # Capture memory usage
    process = psutil.Process(os.getpid())
    mem_mb = process.memory_info().rss / (1024 * 1024)

    print("\n\n" + "=" * 50)
    print("📊 BENCHMARK RESULTS")
    print("=" * 50)
    print(f"Simulated Hardware : {args.cores} CPU Core(s)")
    print(f"Execution Time     : {time_per_image * 1000:.2f} ms per image")
    print(f"Throughput         : {fps:.2f} images / second")
    print(f"Peak RAM Usage     : {mem_mb:.2f} MB")
    print("=" * 50 + "\n")

if __name__ == "__main__":
    main()