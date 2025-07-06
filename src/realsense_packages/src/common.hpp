#ifndef INCLUDE_COMMON_HPP
#define INCLUDE_COMMON_HPP

#include <opencv2/opencv.hpp>

#include <cstdio>
#include <iostream>
#include <fstream>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>
#include <vector>
#include <omp.h>
#include <time.h>
#include <numeric>
#include <algorithm>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <deque>
#include <functional>
#include <random>
#include <bitset>
#include <filesystem>
#include <assert.h>

#include <librealsense2/rs.hpp>
#include "librealsense2/rsutil.h"
#include "structure.hpp"

// よく使う関数のライブラリ
namespace common
{
    // dir + "/000" + var + tag
    std::string make_path(std::string dir, int var, std::string tag)
    {
        std::string back;
        if (var < 10)
        {
            back = dir + "/00000" + std::to_string(var) + tag;
        }
        else if (var < 100)
        {
            back = dir + "/0000" + std::to_string(var) + tag;
        }
        else if (var < 1000)
        {
            back = dir + "/000" + std::to_string(var) + tag;
        }
        else if (var < 10000)
        {
            back = dir + "/00" + std::to_string(var) + tag;
        }
        std::cout << back << std::endl;
        return back;
    }

    void print_elapsed_time(clock_t begin, clock_t end)
    {
        float elapsed = (float)(end - begin) / CLOCKS_PER_SEC;
        printf("Elapsed Time: %15.15f sec\n", elapsed);
    }

    int LBP_filter[3][3] = {{64, 32, 16},
                            {128, 0, 8},
                            {1, 2, 4}};

    // void cvt_ELBP(const cv::Mat &src, cv::Mat &dst, std::vector<int> &UNIFORMED_LUT)
    void cvt_ELBP(const cv::Mat &src, cv::Mat &dst, std::vector<int> &UNIFORMED_LUT)
    {
        cv::Mat lbp = cv::Mat(src.rows, src.cols, CV_8UC1);
        lbp = cv::Scalar::all(0);
        cv::Mat padsrc, gray;
        cv::cvtColor(src, gray, cv::COLOR_BGR2GRAY);
        copyMakeBorder(gray, padsrc, 1, 1, 1, 1, cv::BORDER_REPLICATE);

        // cv::imshow("first", src);
        // cv::imshow("third", lbp);

        int ave = 0;
        for (int x = 1; x < padsrc.cols - 1; x++)
        {
            for (int y = 1; y < padsrc.rows - 1; y++)
            {
                for (int i = 0; i < 3; i++)
                {
                    for (int j = 0; j < 3; j++)
                    {
                        ave += (int)padsrc.at<unsigned char>(y - 1 + j, x - 1 + i);
                    }
                }
                ave /= 8;
                for (int i = 0; i < 3; i++)
                {
                    for (int j = 0; j < 3; j++)
                    {
                        // std::cout << ave << " " << (int)padsrc.at<unsigned char>(y - 1 + j, x - 1 + i) <<std::endl;
                        if (padsrc.at<unsigned char>(y - 1 + j, x - 1 + i) >= ave)
                            lbp.at<unsigned char>(y - 1, x - 1) += LBP_filter[i][j];
                    }
                }
                for (int i = 0; i < 3; i++)
                {
                    for (int j = 0; j < 3; j++)
                    {
                        // std::cout << ave << " " << (int)padsrc.at<unsigned char>(y - 1 + j, x - 1 + i) <<std::endl;
                        lbp.at<unsigned char>(y - 1, x - 1) = UNIFORMED_LUT[lbp.at<unsigned char>(y - 1, x - 1)];
                        // std::cout << (int)lbp.at<unsigned char>(y - 1, x - 1) << std::endl;
                    }
                }
            }
        }
        dst = lbp.clone();
        // cv::imshow("second", lbp);
    }

    void make_LUT(std::vector<int> &lut)
    {
        std::cout << "make_LUT start" << std::endl;
        std::ifstream ifs("data/tools/Uniformed_LBP_Table.txt");
        std::string str;
        int count = 0;
        lut.resize(255);
        if (ifs.fail())
        {
            std::cout << "not lut file" << std::endl;
            return;
        }

        while (getline(ifs, str))
        {
            lut[count] = atoi(str.c_str());
            if (lut[count] != 0)
            {
                double dist = 255 / 35;
                lut[count] = dist * lut[count];
            }
            count++;
        }
        std::cout << "make_LUT end" << std::endl;
    }

    void cvt_depth_edge_image(cv::Mat &edge_image, cv::Mat &depth_image, cv::Mat &result)
    {
        cv::Mat dst = cv::Mat(depth_image.rows, depth_image.cols, CV_8UC3);
        for (int x = 0; x < depth_image.cols; x++)
        {
            for (int y = 0; y < depth_image.rows; y++)
            {
                if (edge_image.at<unsigned char>(y, x) >= 10)
                {
                    dst.at<cv::Vec3b>(y, x) = depth_image.at<cv::Vec3b>(y, x);
                }
                else
                {
                    dst.at<cv::Vec3b>(y, x) = cv::Vec3b(0, 0, 0);
                }
            }
        }

        dst.copyTo(result);
    }

    // librealsense2/rsutil.h
    void deproject_pixel_to_point(float point[3], const struct rs2_intrinsics *intrin, const float pixel[2], float depth)
    {
        assert(intrin->model != RS2_DISTORTION_MODIFIED_BROWN_CONRADY); // Cannot deproject from a forward-distorted image
        // assert(intrin->model != RS2_DISTORTION_BROWN_CONRADY); // Cannot deproject to an brown conrady model

        float x = (pixel[0] - intrin->ppx) / intrin->fx;
        float y = (pixel[1] - intrin->ppy) / intrin->fy;

        float xo = x;
        float yo = y;

        if (intrin->model == RS2_DISTORTION_INVERSE_BROWN_CONRADY)
        {
            // need to loop until convergence
            // 10 iterations determined empirically
            for (int i = 0; i < 10; i++)
            {
                float r2 = x * x + y * y;
                float icdist = (float)1 / (float)(1 + ((intrin->coeffs[4] * r2 + intrin->coeffs[1]) * r2 + intrin->coeffs[0]) * r2);
                float xq = x / icdist;
                float yq = y / icdist;
                float delta_x = 2 * intrin->coeffs[2] * xq * yq + intrin->coeffs[3] * (r2 + 2 * xq * xq);
                float delta_y = 2 * intrin->coeffs[3] * xq * yq + intrin->coeffs[2] * (r2 + 2 * yq * yq);
                x = (xo - delta_x) * icdist;
                y = (yo - delta_y) * icdist;
            }
        }
        if (intrin->model == RS2_DISTORTION_BROWN_CONRADY)
        {
            // need to loop until convergence
            // 10 iterations determined empirically
            for (int i = 0; i < 10; i++)
            {
                float r2 = x * x + y * y;
                float icdist = (float)1 / (float)(1 + ((intrin->coeffs[4] * r2 + intrin->coeffs[1]) * r2 + intrin->coeffs[0]) * r2);
                float delta_x = 2 * intrin->coeffs[2] * x * y + intrin->coeffs[3] * (r2 + 2 * x * x);
                float delta_y = 2 * intrin->coeffs[3] * x * y + intrin->coeffs[2] * (r2 + 2 * y * y);
                x = (xo - delta_x) * icdist;
                y = (yo - delta_y) * icdist;
            }
        }
        if (intrin->model == RS2_DISTORTION_KANNALA_BRANDT4)
        {
            float rd = sqrtf(x * x + y * y);
            if (rd < FLT_EPSILON)
            {
                rd = FLT_EPSILON;
            }

            float theta = rd;
            float theta2 = rd * rd;
            for (int i = 0; i < 4; i++)
            {
                float f = theta * (1 + theta2 * (intrin->coeffs[0] + theta2 * (intrin->coeffs[1] + theta2 * (intrin->coeffs[2] + theta2 * intrin->coeffs[3])))) - rd;
                if (fabs(f) < FLT_EPSILON)
                {
                    break;
                }
                float df = 1 + theta2 * (3 * intrin->coeffs[0] + theta2 * (5 * intrin->coeffs[1] + theta2 * (7 * intrin->coeffs[2] + 9 * theta2 * intrin->coeffs[3])));
                theta -= f / df;
                theta2 = theta * theta;
            }
            float r = tan(theta);
            x *= r / rd;
            y *= r / rd;
        }
        if (intrin->model == RS2_DISTORTION_FTHETA)
        {
            float rd = sqrtf(x * x + y * y);
            if (rd < FLT_EPSILON)
            {
                rd = FLT_EPSILON;
            }
            float r = (float)(tan(intrin->coeffs[0] * rd) / atan(2 * tan(intrin->coeffs[0] / 2.0f)));
            x *= r / rd;
            y *= r / rd;
        }

        point[0] = depth * x;
        point[1] = depth * y;
        point[2] = depth;
    }

    void doDeprojectPosition(const cv::Mat &depth_image, int x, int y, float result[3])
    {
        /****************
        Realsense Internal Parameters
        focus x 614.467
        focus y 614.422
        height width 480 848
        ppx ppy 417.145 242.827
        model Inverse Brown Conrady
        coeffs 0 0
        coeffs 1 0
        coeffs 2 0
        coeffs 3 0
        coeffs 4 0
        ****************/
        rs2_intrinsics intr;
        intr.fx = 614.467;
        intr.fy = 614.422;
        intr.height = 480;
        intr.width = 848;
        intr.ppx = 417.145;
        intr.ppy = 242.827;
        intr.coeffs[0] = 0;
        intr.coeffs[1] = 0;
        intr.coeffs[2] = 0;
        intr.coeffs[3] = 0;
        intr.coeffs[4] = 0;
        intr.model = RS2_DISTORTION_INVERSE_BROWN_CONRADY;

        int x_pix = x;
        int y_pix = y;
        const float pixel[] = {(float)x_pix, (float)y_pix};
        float point[3];
        float dis = depth_image.at<cv::Vec3b>(y_pix, x_pix)[0] * (18200 / 140);

        deproject_pixel_to_point(point, &intr, pixel, dis);

        //std::cout << "[ " << x_pix << "px, " << y_pix << "px , " << dis << " ] = " << "[ " << point[0] << ", " << point[1] << ", " << point[2] << "]" << std::endl;
        ;

        result[0] = point[0];
        result[1] = point[1];
        result[2] = point[2];
    }
};
#endif
