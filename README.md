# FaceAttr-Analysis
This repo is for my adavanced training on deeping learning with the purpose of building a face attributes analysis application.

## File Description

| File/Folder | Description |
| ----------- | ----------- |
| \paper | This folder keeps papers relevant to face attibutes analysis.|
| CelebA.py | This file defines the dataset class for CelebA and provides the data loader function. |
| FaceAttr_baseline_model.py | This file offers the baseline model class, consisting of feature extraction submodel (resnet etc.) and feature classfier submodel (full connect)|
|analysis_attr.py | It reflects the relationship between positive samples and negetive samples in CelebA.|
|solver.py|The file has many functions like initializing, training and evaluating model.|
|main.py| The entry file of project that owns some important variables.|
| logger.py | Use tensorboardX for visualization. |
| sample_num.csv | It records the number of positive and negative samples on every attribute.|

## Dependency
> pip install -r requirements.txt 

## Todo
- [ ] Visualization with [tensorboard](https://github.com/lanpa/tensorboardX) or [netron](https://github.com/lutzroeder/netron). 
- [ ] Try more famous models, such as ResNet50, ResNet101, DenseNet, ResNeXt, SENet.
- [ ] Customize the network structure.
- [ ] Parse the input script command. 
- [ ] Search for the appropriate prediction threshold for every attribute or find a good place to teach themselves.
- [ ] Front end: Video stream monitor[(picamera)](https://github.com/waveform80/picamera) and transfer video frames.
- [ ] Back end: [face detection](https://github.com/ageitgey/face_recognition) and real-time analysis. 

## Done
- [x] [Attribute analysis](https://github.com/JoshuaQYH/FaceAttr-Analysis/blob/master/analysis_attr.py).
- [x] [Data process and load](https://github.com/JoshuaQYH/FaceAttr-Analysis/blob/master/CelebA.py).
- [x] [Built baseline model(Resnet18)](https://github.com/JoshuaQYH/FaceAttr-Analysis/blob/master/FaceAttr_baseline_model.py).
- [x] [Train and evaluate of multiple tasks](https://github.com/JoshuaQYH/FaceAttr-Analysis/blob/master/solver.py). 
- [x] Save and load model.

## License
[MIT](https://github.com/JoshuaQYH/FaceAttr-Analysis/blob/master/LICENSE).
