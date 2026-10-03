# Claim Photo Integrity Detector --- Test Report

## 1. Test Objective

Evaluate the claim-photo integrity detector on the current car-insurance
image dataset and compare its performance on known real photographs
versus known AI-generated/fake photographs.

## 2. Test Setup

-   **Model:** `obuladinnesai/claim-photo-integrity-detector-v1`
-   **Device:** NVIDIA GeForce GTX 1650 via CUDA
-   **Real dataset:** 15 images
-   **Fake/AI-generated dataset:** 10 images
-   **Total test images:** 25
-   **Tile size:** 224 × 224 pixels
-   **Tile overlap:** 25%
-   **Batch size:** 16
-   **Suspicious-tile threshold:** 80%

Each image was divided into overlapping tiles. The model produced an
AI-generation score for every tile. The script then calculated the
average AI score, maximum AI score, top-10%-tile average, and number of
suspicious tiles.

The current decision logic was:

-   **MANIPULATION SUSPECTED** when the maximum AI score was at least
    95% with at least one suspicious tile, or when the top 10% average
    was at least 75%.
-   **REVIEW** when the average AI score was at least 50% and the
    manipulation conditions above were not met.
-   **LIKELY REAL** otherwise.

These decision thresholds are heuristic rules used by the current test
script.

## 3. Overall Results

  Dataset                 Images   Correct   Wrong   Review     Accuracy
  --------------------- -------- --------- ------- -------- ------------
  Real                        15        13       2        0       86.67%
  Fake / AI-generated         10        10       0        0      100.00%
  **Overall**             **25**    **23**   **2**    **0**   **92.00%**

The detector correctly classified 23 of the 25 test images. Both errors
occurred on images in the real-image dataset; all 10 fake/AI-generated
images were detected by the current decision rules.

## 4. Real Image Results

  -------------------------------------------------------------------------------------------------------------------------------------------------------------
         \# Image                                                                              Avg AI    Max AI   Top 10%   Suspicious Decision       Result
                                                                                                                       AI        Tiles                
  --------- ------------------------------------------------------------------------------- --------- --------- --------- ------------ -------------- ---------
          1 360_F_492397454_2QniwEAC2qKa007ntMRzK6WbDGguY2Wh.jpg                               23.64%    84.09%    84.09%            1 MANIPULATION   Wrong
                                                                                                                                       SUSPECTED      

          2 Alto view.jpg                                                                       0.06%     0.21%     0.21%            0 LIKELY REAL    Correct

          3 images (1).jpg                                                                      0.04%     0.10%     0.10%            0 LIKELY REAL    Correct

          4 images (2).jpg                                                                      8.35%    74.94%    74.94%            0 LIKELY REAL    Correct

          5 images (3).jpg                                                                      0.04%     0.19%     0.19%            0 LIKELY REAL    Correct

          6 images (4).jpg                                                                      0.09%     0.49%     0.49%            0 LIKELY REAL    Correct

          7 images (5).jpg                                                                      0.02%     0.03%     0.03%            0 LIKELY REAL    Correct

          8 images (6).jpg                                                                      0.01%     0.02%     0.02%            0 LIKELY REAL    Correct

          9 images (7).jpg                                                                      0.03%     0.08%     0.08%            0 LIKELY REAL    Correct

         10 images (8).jpg                                                                      0.01%     0.01%     0.01%            0 LIKELY REAL    Correct

         11 images.jpg                                                                         16.28%    97.58%    97.58%            1 MANIPULATION   Wrong
                                                                                                                                       SUSPECTED      

         12 maruti-grand-vitara-6.jpg                                                           0.06%     0.33%     0.33%            0 LIKELY REAL    Correct

         13 real-cars-rohini-sector-8-delhi-car-dealers-2p8bz0b.jpg                             0.33%     2.39%     1.82%            0 LIKELY REAL    Correct

         14 tuk-tuk-auto-rickshaw-parking-near-old-delhi-railway-station-india-J66958.jpg       0.79%    22.17%     7.29%            0 LIKELY REAL    Correct

         15 xuv700_11.jpg                                                                       0.01%     0.02%     0.02%            0 LIKELY REAL    Correct
  -------------------------------------------------------------------------------------------------------------------------------------------------------------

### Real-image observations

Most real images produced very low AI scores. Two real images were
flagged as manipulated. In both cases, a small number of high-scoring
tiles caused the final decision even though the whole-image average was
much lower.

The first false positive had an average AI score of 23.64% but a top
score of 84.09%. The second had an average AI score of 16.28% but a
maximum/top score of 97.58%. This indicates that the current tile-based
decision rule can be sensitive to isolated high-scoring regions.

## 5. Fake / AI-Generated Image Results

  ---------------------------------------------------------------------------------------------
         \# Image              Avg AI    Max AI   Top 10%   Suspicious Decision       Result
                                                       AI        Tiles                
  --------- --------------- --------- --------- --------- ------------ -------------- ---------
          1 Crushed Silver     46.60%    99.99%    99.98%           21 MANIPULATION   Correct
            Sedan in Urban                                             SUSPECTED      
            Street.png                                                                

          2 Damaged Royal      27.08%    99.14%    98.34%           10 MANIPULATION   Correct
            Enfield Crash                                              SUSPECTED      
            Aftermath.png                                                             

          3 Damaged Royal      15.50%    99.69%    95.79%            7 MANIPULATION   Correct
            Enfield on Wet                                             SUSPECTED      
            Pavement.png                                                              

          4 Damaged Sedan      84.16%    99.99%    99.99%           43 MANIPULATION   Correct
            on a Tow                                                   SUSPECTED      
            Truck.png                                                                 

          5 Damaged Suzuki     69.81%    99.98%    99.93%           31 MANIPULATION   Correct
            Hatchback on a                                             SUSPECTED      
            Hillside                                                                  
            Road.png                                                                  

          6 Damaged Tata       48.81%    99.97%    99.92%           24 MANIPULATION   Correct
            Truck at                                                   SUSPECTED      
            Highway                                                                   
            Divider.png                                                               

          7 Decorated          25.28%    99.63%    97.23%            7 MANIPULATION   Correct
            Indian Cargo                                               SUSPECTED      
            Truck After                                                               
            Collision.png                                                             

          8 Rear-Left          64.77%    99.99%    99.98%           34 MANIPULATION   Correct
            Hatchback                                                  SUSPECTED      
            Collision                                                                 
            Damage.png                                                                

          9 Wrecked Red        48.42%    99.97%    99.86%           24 MANIPULATION   Correct
            Suzuki on                                                  SUSPECTED      
            Gravel Road.png                                                           

         10 Wrecked Suzuki     66.43%    99.99%    99.98%           30 MANIPULATION   Correct
            on a Mountain                                              SUSPECTED      
            Road.png                                                                  
  ---------------------------------------------------------------------------------------------

### Fake-image observations

All 10 fake/AI-generated images were detected by the current rules.
Every fake image contained at least one region with a very high AI
score, and the maximum AI scores ranged from 99.14% to 99.99%.

The whole-image average varied substantially---from 15.50% to
84.16%---which shows why regional/tile analysis can reveal suspicious
regions even when the average score across the complete image is
relatively low.

## 6. Confusion Summary

Using **LIKELY REAL** as a real prediction and **MANIPULATION
SUSPECTED** as a fake prediction:

  Actual / Predicted     Real   Fake
  -------------------- ------ ------
  Actual Real              13      2
  Actual Fake               0     10

For this 25-image dataset:

-   **True real classifications:** 13
-   **False manipulation flags:** 2
-   **Detected fake images:** 10
-   **Missed fake images:** 0

There were no `REVIEW` outcomes in this run.

## 7. Conclusion

On the current test dataset, the claim-photo integrity detector achieved
**92.00% overall accuracy**, with **86.67% accuracy on real images** and
**100.00% accuracy on the fake/AI-generated images**.

The strongest result in this run is that all 10 known fake images were
flagged. The main observed weakness was false positives on real images:
2 of 15 real images were marked as manipulation suspected because of
isolated high-scoring tiles.

These results describe only this specific 25-image test set and should
not be interpreted as the model's general real-world accuracy. A larger
and more diverse claim-photo dataset would be needed for stronger
evaluation and for tuning the decision thresholds.
