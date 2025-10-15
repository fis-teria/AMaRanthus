#include <cuda_runtime.h>
#include <math_constants.h>
#include <stdint.h>

extern "C" __global__
void count_hits_kernel(const float* __restrict__ xs,
                       const float* __restrict__ ys,
                       const float* __restrict__ zs,
                       int n_points,
                       float origin_x, float origin_y,
                       float res, int width, int height,
                       float z_min, float z_max, float obs_min_h,
                       unsigned int* __restrict__ counts) {
  int i = blockIdx.x * blockDim.x + threadIdx.x;
  if (i >= n_points) return;

  float x = xs[i];
  float y = ys[i];
  float z = zs[i];

  // 基本的な NaN/inf ガード
  if (!isfinite(x) || !isfinite(y) || !isfinite(z)) return;

  // z フィルタ
  if (z < z_min || z > z_max) return;
  if (z < obs_min_h) return;

  // グリッド座標
  int ix = __float2int_rd((x - origin_x) / res); // floor
  int iy = __float2int_rd((y - origin_y) / res);
  if (ix < 0 || ix >= width || iy < 0 || iy >= height) return;

  int idx = iy * width + ix;
  atomicAdd(&counts[idx], 1u);
}

extern "C" cudaError_t launch_count_hits(
    const float* xs, const float* ys, const float* zs, int n_points,
    float origin_x, float origin_y, float res, int width, int height,
    float z_min, float z_max, float obs_min_h,
    unsigned int* counts, cudaStream_t stream) {

  int threads = 256;
  int blocks  = (n_points + threads - 1) / threads;
  count_hits_kernel<<<blocks, threads, 0, stream>>>(
      xs, ys, zs, n_points, origin_x, origin_y, res, width, height,
      z_min, z_max, obs_min_h, counts);
  return cudaGetLastError();
}
