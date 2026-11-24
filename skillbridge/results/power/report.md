# Power analysis (simulation)

1000 simulated studies per cell; Wilcoxon signed-rank at alpha = 0.0167 (Holm, 3 judges).

## Power to detect the term penalty (25 items, 5 repeats)

Rows: mean true penalty in rubric points. Columns: (SD of the penalty between terms, judge noise SD between repeats).

|   true_penalty |   (0.0, 0.3) |   (0.0, 0.45) |   (0.0, 0.7) |   (0.3, 0.3) |   (0.3, 0.45) |   (0.3, 0.7) |
|---------------:|-------------:|--------------:|-------------:|-------------:|--------------:|-------------:|
|           0.00 |         0.02 |          0.02 |         0.01 |         0.01 |          0.02 |         0.01 |
|           0.10 |         0.52 |          0.28 |         0.13 |         0.12 |          0.13 |         0.09 |
|           0.20 |         0.99 |          0.91 |         0.60 |         0.59 |          0.49 |         0.36 |
|           0.25 |         1.00 |          0.99 |         0.80 |         0.79 |          0.72 |         0.50 |
|           0.30 |         1.00 |          1.00 |         0.94 |         0.93 |          0.90 |         0.72 |
|           0.40 |         1.00 |          1.00 |         1.00 |         1.00 |          0.99 |         0.95 |
|           0.50 |         1.00 |          1.00 |         1.00 |         1.00 |          1.00 |         0.99 |

## Power of the TOST equivalence test (bounds ±0.25) when the true penalty is 0 for every term

|         |   0.3 |   0.45 |   0.7 |
|:--------|------:|-------:|------:|
| (25, 3) |  1.00 |   0.99 |  0.85 |
| (25, 5) |  1.00 |   1.00 |  0.98 |
| (40, 3) |  1.00 |   1.00 |  0.98 |
| (40, 5) |  1.00 |   1.00 |  1.00 |

Full grid (also 40 items and 3 repeats): `power.csv`.