#ifndef STRUCTURE_HPP
#define STRUCTURE_HPP
#include<opencv2/opencv.hpp>

class ResultImage{
    public:
    cv::Mat image;
    int xmin;
    int xmax;
    int ymin;
    int ymax;
    int id;
    
    ResultImage(){

    }

    void get_data(){
        std::cout << "*********result data*********\n";
        std::cout << "image size [cols, rows] = [" << image.cols << " x " << image.rows << "]\n";
        std::cout << "trimming area [xmin, xmax, ymin, ymax] = [" << xmin << ", " << xmax << ", "  << ymin << ", " << ymax << "]\n";
        std::cout << "label id = " << id << std::endl;
        std::cout << "*****************************" << std::endl;
    }
};

#endif