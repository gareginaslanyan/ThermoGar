| база | состав | добавка по умолчанию (фазы умолчания) | T, °C | фазы (мольн. доли) | добавка в фазах с прямой/унаследованной DP-моделью, мольн. доля | ρ программа, кг/м³ | ρ своя модель, кг/м³ | Δ, кг/м³ | Δ, % | Δ выкл., % | метка |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fe | 316L_HCP | CR (HCP_A3; своя: DP(BCC_A2,CR:VA) (reference)); FE (HCP_A3; своя: DP(BCC_A2,FE:VA) (reference)); MO (HCP_A3; своя: DP(BCC_A2,MO:VA) (reference)); NI (HCP_A3; своя: DP(FCC_A1,NI:VA) (matrix)) | 25 | BCC_B2 0.182 [BCC_A2], BCC_DISL 0.00573 [—], FCC_A1 0.00749, GAMMA_PRIME 0.188 [FCC_A1], H_BCC 0.559 [—], SIGMA 0.0577 [—] | 0.376 | — | — | — | — | — |  |
| fe | 316L_HCP | CR (HCP_A3; своя: DP(BCC_A2,CR:VA) (reference)); FE (HCP_A3; своя: DP(BCC_A2,FE:VA) (reference)); MO (HCP_A3; своя: DP(BCC_A2,MO:VA) (reference)); NI (HCP_A3; своя: DP(FCC_A1,NI:VA) (matrix)) | 800 | CHI_A12 0.035 [—], FCC_A1 0.963, M23C6 0.00176 | 0.961 | 7736.94 | 7736.94 | 0.00 | +0.000 | +0.000 |  |
| fe | 316L_HCP | CR (HCP_A3; своя: DP(BCC_A2,CR:VA) (reference)); FE (HCP_A3; своя: DP(BCC_A2,FE:VA) (reference)); MO (HCP_A3; своя: DP(BCC_A2,MO:VA) (reference)); NI (HCP_A3; своя: DP(FCC_A1,NI:VA) (matrix)) | 1000 | FCC_A1 1 | 0.997 | 7658.41 | 7658.41 | 0.00 | +0.000 | +0.000 |  |
| ni | IN738_bez_Ta | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)); B (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0TETR_B (function, D0 при 298,15 K, без расширения)) | 25 | CR2B 0.00156 [—], GAMMA_PRIME 0.645 [FCC_A1], HCP_A3 0.00222, M23C6 0.0249, NI2CR 0.215 [—], P_PHASE 0.0371 [—], SIGMA 0.0738 [—] | 0.000308 | 7877.09 | 7876.18 | 0.91 | +0.012 | +0.012 |  |
| ni | IN738_bez_Ta | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)); B (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0TETR_B (function, D0 при 298,15 K, без расширения)) | 800 | FCC_A1 0.477, GAMMA_PRIME 0.498 [FCC_A1], M23C6 0.0249, TIB2 0.000766 [—] | 0.000313 | 7731.40 | 7730.64 | 0.76 | +0.010 | +0.010 |  |
| ni | IN738_bez_Ta | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)); B (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0TETR_B (function, D0 при 298,15 K, без расширения)) | 1000 | GAMMA_DP 0.0927 [—], GAMMA_PRIME 0.882 [FCC_A1], M23C6 0.0249, TIB2 0.00076 [—] | 0.000308 | 7666.12 | 7665.39 | 0.72 | +0.009 | +0.009 |  |
| al | V96c1och | ZN (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZN:VA) (reference)) | 25 | AL12MN 0.0239 [—], GP_MAT 0.884 [FCC_A1], LC14_ZN2MG 0.0605 [—], MG2SI_B 0.00154 [—], MGALCUZN_T 0.0176 [—], S_PHASE 0.0121 [—] | 2.04e-05 | 2857.27 | 2857.26 | 0.01 | +0.000 | +0.000 |  |
| al | V96c1och | ZN (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZN:VA) (reference)) | 300 | ALCRFEMNSI_A 0.0107 [—], GP_MAT 0.916 [FCC_A1], LC14_ZN2MG 0.0469 [—], MG2SI_B 4.2e-05 [—], MGALCUZN_T 0.0189 [—], S_PHASE 0.00752 [—] | 0.00744 | 2793.33 | 2790.87 | 2.46 | +0.088 | +0.088 |  |
| al | V96c1och | ZN (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZN:VA) (reference)) | 500 | ALCUMN_T1 0.0112 [—], GP_MAT 0.978 [FCC_A1], MG2SI_B 0.000809 [—], MGALCUZN_T 0.00765 [—], S_PHASE 0.00206 [—] | 0.0343 | 2733.39 | 2721.66 | 11.73 | +0.431 | +0.431 | > 0,1 % |
| al | V96c1och | ZN (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZN:VA) (reference)) | 800 | LIQUID 1 | 0.037 | 2669.52 | 2657.04 | 12.48 | +0.470 | +0.470 | > 0,1 % |
| al | AL-0.1SC | SC (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0HCP_SC+DTSCHCP (function, D0 при 298,15 K + DT)) | 25 | AL3SC 0.0024 [—], FCCAL 0.998 [FCC_A1] | 0 | 2698.19 | 2698.19 | 0.00 | +0.000 | +0.000 |  |
| al | AL-0.1SC | SC (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0HCP_SC+DTSCHCP (function, D0 при 298,15 K + DT)) | 300 | AL3SC 0.00235 [—], GP_MAT 0.998 [FCC_A1] | 1.28e-05 | 2643.00 | 2643.01 | -0.01 | -0.000 | -0.000 |  |
| al | AL-0.1SC | SC (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0HCP_SC+DTSCHCP (function, D0 при 298,15 K + DT)) | 500 | AL3SC 0.000923 [—], GP_MAT 0.999 [FCC_A1] | 0.00037 | 2595.30 | 2595.49 | -0.19 | -0.007 | -0.007 |  |
| al | AL-0.1SC | SC (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0HCP_SC+DTSCHCP (function, D0 при 298,15 K + DT)) | 800 | LIQUID 1 | 0.0006 | 2512.30 | 2512.64 | -0.34 | -0.013 | -0.013 |  |
| al | AL-0.5SC | SC (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0HCP_SC+DTSCHCP (function, D0 при 298,15 K + DT)) | 25 | AL3SC 0.012 [—], FCCAL 0.988 [FCC_A1] | 0 | 2699.24 | 2699.24 | 0.00 | +0.000 | +0.000 |  |
| al | AL-0.5SC | SC (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0HCP_SC+DTSCHCP (function, D0 при 298,15 K + DT)) | 300 | AL3SC 0.012 [—], GP_MAT 0.988 [FCC_A1] | 1.27e-05 | 2644.14 | 2644.15 | -0.01 | -0.000 | -0.000 |  |
| al | AL-0.5SC | SC (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0HCP_SC+DTSCHCP (function, D0 при 298,15 K + DT)) | 500 | AL3SC 0.0106 [—], GP_MAT 0.989 [FCC_A1] | 0.000366 | 2596.52 | 2596.71 | -0.19 | -0.007 | -0.007 |  |
| al | AL-0.5SC | SC (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0HCP_SC+DTSCHCP (function, D0 при 298,15 K + DT)) | 800 | LIQUID 1 | 0.00301 | — | 2514.00 | — | — | — |  |
| al | AL-1SC | SC (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0HCP_SC+DTSCHCP (function, D0 при 298,15 K + DT)) | 25 | AL3SC 0.0241 [—], FCCAL 0.976 [FCC_A1] | 0 | 2700.55 | 2700.55 | 0.00 | +0.000 | +0.000 |  |
| al | AL-1SC | SC (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0HCP_SC+DTSCHCP (function, D0 при 298,15 K + DT)) | 300 | AL3SC 0.0241 [—], GP_MAT 0.976 [FCC_A1] | 1.25e-05 | 2645.57 | 2645.57 | -0.01 | -0.000 | -0.000 |  |
| al | AL-1SC | SC (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0HCP_SC+DTSCHCP (function, D0 при 298,15 K + DT)) | 500 | AL3SC 0.0227 [—], GP_MAT 0.977 [FCC_A1] | 0.000362 | 2598.05 | 2598.23 | -0.18 | -0.007 | -0.007 |  |
| al | AL-1SC | SC (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0HCP_SC+DTSCHCP (function, D0 при 298,15 K + DT)) | 800 | LIQUID 1 | 0.00603 | — | 2515.70 | — | — | — |  |
| al | AL-2SC | SC (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0HCP_SC+DTSCHCP (function, D0 при 298,15 K + DT)) | 25 | AL3SC 0.0484 [—], FCCAL 0.952 [FCC_A1] | 0 | 2703.17 | 2703.17 | 0.00 | +0.000 | +0.000 |  |
| al | AL-2SC | SC (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0HCP_SC+DTSCHCP (function, D0 при 298,15 K + DT)) | 300 | AL3SC 0.0484 [—], GP_MAT 0.952 [FCC_A1] | 1.22e-05 | 2648.43 | 2648.43 | -0.01 | -0.000 | -0.000 |  |
| al | AL-2SC | SC (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0HCP_SC+DTSCHCP (function, D0 при 298,15 K + DT)) | 500 | AL3SC 0.047 [—], GP_MAT 0.953 [FCC_A1] | 0.000353 | 2601.12 | 2601.30 | -0.18 | -0.007 | -0.007 |  |
| al | AL-2SC | SC (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0HCP_SC+DTSCHCP (function, D0 при 298,15 K + DT)) | 800 | AL3SC 0.0218 [—], LIQUID 0.978 | 0.00665 | — | 2519.10 | — | — | — |  |
| al | AL-0.1ZN | ZN (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZN:VA) (reference)) | 25 | GP_MAT 1 | 0 | 2699.74 | 2699.61 | 0.13 | +0.005 | +0.005 |  |
| al | AL-0.1ZN | ZN (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZN:VA) (reference)) | 300 | GP_MAT 1 | 0 | 2644.49 | 2644.36 | 0.13 | +0.005 | +0.005 |  |
| al | AL-0.1ZN | ZN (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZN:VA) (reference)) | 500 | GP_MAT 1 | 0 | 2596.92 | 2596.79 | 0.13 | +0.005 | +0.005 |  |
| al | AL-0.1ZN | ZN (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZN:VA) (reference)) | 800 | LIQUID 1 | 0.000413 | 2513.99 | 2513.86 | 0.13 | +0.005 | +0.005 |  |
| al | AL-0.5ZN | ZN (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZN:VA) (reference)) | 25 | GP_MAT 1 | 0 | 2706.98 | 2706.35 | 0.63 | +0.023 | +0.023 |  |
| al | AL-0.5ZN | ZN (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZN:VA) (reference)) | 300 | GP_MAT 1 | 0 | 2651.59 | 2650.94 | 0.65 | +0.025 | +0.025 |  |
| al | AL-0.5ZN | ZN (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZN:VA) (reference)) | 500 | GP_MAT 1 | 0 | 2603.91 | 2603.24 | 0.67 | +0.026 | +0.026 |  |
| al | AL-0.5ZN | ZN (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZN:VA) (reference)) | 800 | LIQUID 1 | 0.00207 | 2520.76 | 2520.10 | 0.66 | +0.026 | +0.026 |  |
| al | AL-1ZN | ZN (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZN:VA) (reference)) | 25 | GP_MAT 1 | 0 | 2716.09 | 2714.82 | 1.27 | +0.047 | +0.047 |  |
| al | AL-1ZN | ZN (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZN:VA) (reference)) | 300 | GP_MAT 1 | 0 | 2660.52 | 2659.21 | 1.31 | +0.049 | +0.049 |  |
| al | AL-1ZN | ZN (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZN:VA) (reference)) | 500 | GP_MAT 1 | 0 | 2612.70 | 2611.35 | 1.35 | +0.052 | +0.052 |  |
| al | AL-1ZN | ZN (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZN:VA) (reference)) | 800 | LIQUID 1 | 0.00415 | 2529.28 | 2527.94 | 1.34 | +0.053 | +0.053 |  |
| al | AL-2ZN | ZN (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZN:VA) (reference)) | 25 |  | 0 | — | — | — | — | — |  |
| al | AL-2ZN | ZN (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZN:VA) (reference)) | 300 | GP_MAT 1 | 0 | 2678.57 | 2675.90 | 2.66 | +0.099 | +0.099 |  |
| al | AL-2ZN | ZN (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZN:VA) (reference)) | 500 | GP_MAT 1 | 0 | 2630.45 | 2627.72 | 2.74 | +0.104 | +0.104 | > 0,1 % |
| al | AL-2ZN | ZN (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZN:VA) (reference)) | 800 | LIQUID 1 | 0.00835 | 2546.48 | 2543.78 | 2.71 | +0.106 | +0.106 | > 0,1 % |
| al | AL-0.1ZR | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)) | 25 | AL3ZR 0.00118 [—], FCCAL 0.999 [FCC_A1] | 0 | 2699.52 | 2699.52 | 0.00 | +0.000 | +0.000 |  |
| al | AL-0.1ZR | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)) | 300 | AL3ZR 0.00118 [—], GP_MAT 0.999 [FCC_A1] | 2.1e-06 | 2644.30 | 2644.30 | 0.00 | +0.000 | +0.000 |  |
| al | AL-0.1ZR | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)) | 500 | AL3ZR 0.000886 [—], GP_MAT 0.999 [FCC_A1] | 7.46e-05 | 2596.79 | 2596.74 | 0.05 | +0.002 | +0.002 |  |
| al | AL-0.1ZR | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)) | 800 | LIQUID 1 | 0.000296 | 2513.99 | 2513.84 | 0.15 | +0.006 | +0.006 |  |
| al | AL-0.5ZR | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)) | 25 | AL3ZR 0.00594 [—], FCCAL 0.994 [FCC_A1] | 0 | 2705.90 | 2705.90 | 0.00 | +0.000 | +0.000 |  |
| al | AL-0.5ZR | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)) | 300 | AL3ZR 0.00593 [—], GP_MAT 0.994 [FCC_A1] | 2.09e-06 | 2650.61 | 2650.61 | 0.00 | +0.000 | +0.000 |  |
| al | AL-0.5ZR | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)) | 500 | AL3ZR 0.00564 [—], GP_MAT 0.994 [FCC_A1] | 7.42e-05 | 2603.04 | 2602.99 | 0.05 | +0.002 | +0.002 |  |
| al | AL-0.5ZR | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)) | 800 | LIQUID 1 | 0.00148 | 2520.76 | 2519.99 | 0.77 | +0.031 | +0.031 |  |
| al | AL-1ZR | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)) | 25 | AL3ZR 0.0119 [—], FCCAL 0.988 [FCC_A1] | 0 | 2713.92 | 2713.92 | 0.00 | +0.000 | +0.000 |  |
| al | AL-1ZR | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)) | 300 | AL3ZR 0.0119 [—], GP_MAT 0.988 [FCC_A1] | 2.08e-06 | 2658.54 | 2658.54 | 0.00 | +0.000 | +0.000 |  |
| al | AL-1ZR | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)) | 500 | AL3ZR 0.0116 [—], GP_MAT 0.988 [FCC_A1] | 7.38e-05 | 2610.90 | 2610.86 | 0.05 | +0.002 | +0.002 |  |
| al | AL-1ZR | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)) | 800 | LIQUID 1 | 0.00298 | 2529.28 | 2527.72 | 1.55 | +0.061 | +0.061 |  |
| al | AL-2ZR | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)) | 25 | AL3ZR 0.024 [—], FCCAL 0.976 [FCC_A1] | 0 | 2730.10 | 2730.10 | 0.00 | +0.000 | +0.000 |  |
| al | AL-2ZR | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)) | 300 | AL3ZR 0.024 [—], GP_MAT 0.976 [FCC_A1] | 2.05e-06 | 2674.55 | 2674.55 | 0.00 | +0.000 | +0.000 |  |
| al | AL-2ZR | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)) | 500 | AL3ZR 0.0237 [—], GP_MAT 0.976 [FCC_A1] | 7.29e-05 | 2626.77 | 2626.72 | 0.05 | +0.002 | +0.002 |  |
| al | AL-2ZR | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)) | 800 | LIQUID 1 | 0.006 | 2546.48 | 2543.34 | 3.15 | +0.124 | +0.124 | > 0,1 % |
| fe | FE-0.1HF | HF (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 25 | BCC_B2 1 [BCC_A2] | 0.000313 | 7876.16 | 7879.37 | -3.22 | -0.041 | -0.041 |  |
| fe | FE-0.1HF | HF (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 800 | BCC_B2 1 [BCC_A2] | 0.000313 | 7606.40 | 7609.66 | -3.26 | -0.043 | -0.043 |  |
| fe | FE-0.1HF | HF (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 1000 | FCC_A1 1 | 0.000313 | 7606.59 | 7609.85 | -3.26 | -0.043 | -0.043 |  |
| fe | FE-0.5HF | HF (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 25 | BCC_B2 1 [BCC_A2] | 0.00157 | 7876.16 | 7892.27 | -16.11 | -0.204 | -0.204 | > 0,1 % |
| fe | FE-0.5HF | HF (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 800 | BCC_B2 1 [BCC_A2] | 0.00157 | 7606.40 | 7622.73 | -16.33 | -0.214 | -0.214 | > 0,1 % |
| fe | FE-0.5HF | HF (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 1000 | FCC_A1 1 | 0.00157 | 7606.59 | 7622.92 | -16.33 | -0.214 | -0.214 | > 0,1 % |
| fe | FE-1HF | HF (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 25 | BCC_B2 1 [BCC_A2] | 0.00315 | 7876.16 | 7908.44 | -32.29 | -0.408 | -0.408 | > 0,1 % |
| fe | FE-1HF | HF (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 800 | BCC_B2 1 [BCC_A2] | 0.00315 | 7606.40 | 7639.13 | -32.74 | -0.429 | -0.429 | > 0,1 % |
| fe | FE-1HF | HF (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 1000 | FCC_A1 1 | 0.00315 | 7606.59 | 7639.32 | -32.74 | -0.429 | -0.429 | > 0,1 % |
| fe | FE-2HF | HF (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 25 | BCC_B2 1 [BCC_A2] | 0.00634 | 7876.16 | 7941.00 | -64.84 | -0.817 | -0.817 | **> 0,5 %** |
| fe | FE-2HF | HF (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 800 | BCC_B2 1 [BCC_A2] | 0.00634 | 7606.40 | 7672.15 | -65.76 | -0.857 | -0.857 | **> 0,5 %** |
| fe | FE-2HF | HF (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 1000 | FCC_A1 1 | 0.00634 | 7606.59 | 7672.34 | -65.76 | -0.857 | -0.857 | **> 0,5 %** |
| fe | FE-0.1LA | LA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_LA (function, D0 при 298,15 K, без расширения)) | 25 | FCC_A1 0.000402, H_BCC 1 [—] | 0.000402 | 7876.41 | 7873.96 | 2.45 | +0.031 | +0.031 |  |
| fe | FE-0.1LA | LA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_LA (function, D0 при 298,15 K, без расширения)) | 800 | BCC_B2 1 [BCC_A2] | 0.000402 | 7606.40 | 7604.61 | 1.79 | +0.023 | +0.023 |  |
| fe | FE-0.1LA | LA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_LA (function, D0 при 298,15 K, без расширения)) | 1000 | FCC_A1 1 | 0.000402 | 7606.59 | 7604.80 | 1.79 | +0.023 | +0.023 |  |
| fe | FE-0.5LA | LA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_LA (function, D0 при 298,15 K, без расширения)) | 25 | FCC_A1 0.00202, H_BCC 0.998 [—] | 0.00202 | 7877.43 | 7865.20 | 12.23 | +0.156 | +0.156 | > 0,1 % |
| fe | FE-0.5LA | LA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_LA (function, D0 при 298,15 K, без расширения)) | 800 | BCC_B2 0.999 [BCC_A2], FCC_A1 0.000624 | 0.00202 | 7606.56 | 7597.48 | 9.08 | +0.120 | +0.120 | > 0,1 % |
| fe | FE-0.5LA | LA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_LA (function, D0 при 298,15 K, без расширения)) | 1000 | FCC_A1 1, LIQUID 1.6e-05 | 0.00202 | 7606.58 | 7597.67 | 8.92 | +0.117 | +0.117 | > 0,1 % |
| fe | FE-1LA | LA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_LA (function, D0 при 298,15 K, без расширения)) | 25 | FCC_A1 0.00404, H_BCC 0.996 [—] | 0.00404 | 7878.71 | 7854.27 | 24.44 | +0.311 | +0.311 | > 0,1 % |
| fe | FE-1LA | LA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_LA (function, D0 при 298,15 K, без расширения)) | 800 | BCC_B2 0.997 [BCC_A2], FCC_A1 0.00266 | 0.00404 | 7607.09 | 7588.58 | 18.51 | +0.244 | +0.244 | > 0,1 % |
| fe | FE-1LA | LA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_LA (function, D0 при 298,15 K, без расширения)) | 1000 | FCC_A1 0.997, LIQUID 0.00265 | 0.00404 | 7605.81 | 7588.68 | 17.13 | +0.226 | +0.226 | > 0,1 % |
| fe | FE-2LA | LA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_LA (function, D0 при 298,15 K, без расширения)) | 25 | FCC_A1 0.00814, H_BCC 0.992 [—] | 0.00814 | 7881.27 | 7832.51 | 48.76 | +0.622 | +0.622 | **> 0,5 %** |
| fe | FE-2LA | LA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_LA (function, D0 при 298,15 K, без расширения)) | 800 | BCC_B2 0.993 [BCC_A2], FCC_A1 0.00676 | 0.00814 | 7608.14 | 7570.84 | 37.30 | +0.493 | +0.493 | > 0,1 % |
| fe | FE-2LA | LA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_LA (function, D0 при 298,15 K, без расширения)) | 1000 | FCC_A1 0.992, LIQUID 0.00798 | 0.00814 | 7604.27 | 7570.78 | 33.49 | +0.442 | +0.442 | > 0,1 % |
| fe | FE-0.1P | P (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0MONO_P (function, D0 при 298,15 K, без расширения)) | 25 | H_BCC 0.993 [—], M3P 0.00721 [—] | 0 | 7850.03 | 7850.03 | 0.00 | +0.000 | +0.000 |  |
| fe | FE-0.1P | P (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0MONO_P (function, D0 при 298,15 K, без расширения)) | 800 | BCC_B2 1 [BCC_A2] | 0.0018 | 7606.40 | 7582.29 | 24.11 | +0.318 | +0.318 | > 0,1 % |
| fe | FE-0.1P | P (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0MONO_P (function, D0 при 298,15 K, без расширения)) | 1000 | FCC_A1 1 | 0.0018 | 7606.59 | 7582.48 | 24.11 | +0.318 | +0.318 | > 0,1 % |
| fe | FE-0.5P | P (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0MONO_P (function, D0 при 298,15 K, без расширения)) | 25 | H_BCC 0.964 [—], M3P 0.0359 [—] | 0 | 7747.25 | 7747.25 | 0.00 | +0.000 | +0.000 |  |
| fe | FE-0.5P | P (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0MONO_P (function, D0 при 298,15 K, без расширения)) | 800 | BCC_B2 1 [BCC_A2] | 0.00898 | 7606.40 | 7487.37 | 119.03 | +1.590 | +1.590 | **> 0,5 %** |
| fe | FE-0.5P | P (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0MONO_P (function, D0 при 298,15 K, без расширения)) | 1000 | BCC_B2 0.979 [BCC_A2], FCC_A1 0.021 | 0.00898 | 7527.20 | 7411.00 | 116.20 | +1.568 | +1.568 | **> 0,5 %** |
| fe | FE-1P | P (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0MONO_P (function, D0 при 298,15 K, без расширения)) | 25 | H_BCC 0.928 [—], M3P 0.0715 [—] | 0 | 7622.50 | 7622.50 | 0.00 | +0.000 | +0.000 |  |
| fe | FE-1P | P (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0MONO_P (function, D0 при 298,15 K, без расширения)) | 800 | BCC_B2 1 [BCC_A2] | 0.0179 | 7606.40 | 7372.01 | 234.39 | +3.179 | +3.179 | **> 0,5 %** |
| fe | FE-1P | P (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0MONO_P (function, D0 при 298,15 K, без расширения)) | 1000 | BCC_B2 1 [BCC_A2] | 0.0179 | 7525.51 | 7296.76 | 228.75 | +3.135 | +3.135 | **> 0,5 %** |
| fe | FE-2P | P (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0MONO_P (function, D0 при 298,15 K, без расширения)) | 25 | H_BCC 0.858 [—], M3P 0.142 [—] | 0 | 7384.68 | 7384.68 | 0.00 | +0.000 | +0.000 |  |
| fe | FE-2P | P (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0MONO_P (function, D0 при 298,15 K, без расширения)) | 800 | BCC_B2 1 [BCC_A2] | 0.0355 | 7606.40 | 7151.63 | 454.77 | +6.359 | +6.359 | **> 0,5 %** |
| fe | FE-2P | P (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0MONO_P (function, D0 при 298,15 K, без расширения)) | 1000 | BCC_B2 1 [BCC_A2] | 0.0355 | 7525.51 | 7081.50 | 444.01 | +6.270 | +6.270 | **> 0,5 %** |
| fe | FE-0.1PD | PD (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_PD (function, D0 при 298,15 K, без расширения)) | 25 | H_BCC 0.999 [—], PDMN_P 0.00095 [—] | 0 | 7878.87 | 7878.87 | 0.00 | +0.000 | +0.000 |  |
| fe | FE-0.1PD | PD (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_PD (function, D0 при 298,15 K, без расширения)) | 800 | BCC_B2 1 [BCC_A2] | 0.000525 | 7606.40 | 7609.19 | -2.79 | -0.037 | -0.037 |  |
| fe | FE-0.1PD | PD (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_PD (function, D0 при 298,15 K, без расширения)) | 1000 | FCC_A1 1 | 0.000525 | 7606.59 | 7609.38 | -2.79 | -0.037 | -0.037 |  |
| fe | FE-0.5PD | PD (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_PD (function, D0 при 298,15 K, без расширения)) | 25 | H_BCC 0.995 [—], PDMN_P 0.00476 [—] | 0 | 7889.76 | 7889.76 | 0.00 | +0.000 | +0.000 |  |
| fe | FE-0.5PD | PD (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_PD (function, D0 при 298,15 K, без расширения)) | 800 | BCC_B2 1 [BCC_A2] | 0.00263 | 7606.40 | 7620.39 | -13.99 | -0.184 | -0.184 | > 0,1 % |
| fe | FE-0.5PD | PD (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_PD (function, D0 при 298,15 K, без расширения)) | 1000 | FCC_A1 1 | 0.00263 | 7606.59 | 7620.58 | -13.99 | -0.184 | -0.184 | > 0,1 % |
| fe | FE-1PD | PD (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_PD (function, D0 при 298,15 K, без расширения)) | 25 | H_BCC 0.99 [—], PDMN_P 0.00954 [—] | 0 | 7903.40 | 7903.40 | 0.00 | +0.000 | +0.000 |  |
| fe | FE-1PD | PD (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_PD (function, D0 при 298,15 K, без расширения)) | 800 | BCC_B2 1 [BCC_A2] | 0.00527 | 7606.40 | 7634.43 | -28.03 | -0.367 | -0.367 | > 0,1 % |
| fe | FE-1PD | PD (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_PD (function, D0 при 298,15 K, без расширения)) | 1000 | FCC_A1 1 | 0.00527 | 7606.59 | 7634.62 | -28.03 | -0.367 | -0.367 | > 0,1 % |
| fe | FE-2PD | PD (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_PD (function, D0 при 298,15 K, без расширения)) | 25 | H_BCC 0.981 [—], PDMN_P 0.0192 [—] | 0 | 7930.84 | 7930.84 | 0.00 | +0.000 | +0.000 |  |
| fe | FE-2PD | PD (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_PD (function, D0 при 298,15 K, без расширения)) | 800 | BCC_B2 1 [BCC_A2] | 0.0106 | 7606.40 | 7662.67 | -56.27 | -0.734 | -0.734 | **> 0,5 %** |
| fe | FE-2PD | PD (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_PD (function, D0 при 298,15 K, без расширения)) | 1000 | FCC_A1 1 | 0.0106 | 7606.59 | 7662.86 | -56.27 | -0.734 | -0.734 | **> 0,5 %** |
| fe | FE-0.1TA | TA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0BCC_TA (function, D0 при 298,15 K, без расширения)) | 25 | BCC_B2 1 [BCC_A2] | 0.000309 | 7876.16 | 7880.31 | -4.16 | -0.053 | -0.053 |  |
| fe | FE-0.1TA | TA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0BCC_TA (function, D0 при 298,15 K, без расширения)) | 800 | BCC_B2 1 [BCC_A2] | 0.000309 | 7606.40 | 7610.54 | -4.14 | -0.054 | -0.054 |  |
| fe | FE-0.1TA | TA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0BCC_TA (function, D0 при 298,15 K, без расширения)) | 1000 | FCC_A1 1 | 0.000309 | 7606.59 | 7610.73 | -4.14 | -0.054 | -0.054 |  |
| fe | FE-0.5TA | TA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0BCC_TA (function, D0 при 298,15 K, без расширения)) | 25 | BCC_B2 1 [BCC_A2] | 0.00155 | 7876.16 | 7897.00 | -20.84 | -0.264 | -0.264 | > 0,1 % |
| fe | FE-0.5TA | TA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0BCC_TA (function, D0 при 298,15 K, без расширения)) | 800 | BCC_B2 1 [BCC_A2] | 0.00155 | 7606.40 | 7627.14 | -20.75 | -0.272 | -0.272 | > 0,1 % |
| fe | FE-0.5TA | TA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0BCC_TA (function, D0 при 298,15 K, без расширения)) | 1000 | FCC_A1 1 | 0.00155 | 7606.59 | 7627.33 | -20.75 | -0.272 | -0.272 | > 0,1 % |
| fe | FE-1TA | TA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0BCC_TA (function, D0 при 298,15 K, без расширения)) | 25 | BCC_B2 1 [BCC_A2] | 0.00311 | 7876.16 | 7917.95 | -41.79 | -0.528 | -0.528 | **> 0,5 %** |
| fe | FE-1TA | TA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0BCC_TA (function, D0 при 298,15 K, без расширения)) | 800 | BCC_B2 1 [BCC_A2] | 0.00311 | 7606.40 | 7648.00 | -41.61 | -0.544 | -0.544 | **> 0,5 %** |
| fe | FE-1TA | TA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0BCC_TA (function, D0 при 298,15 K, без расширения)) | 1000 | FCC_A1 1 | 0.00311 | 7606.59 | 7648.19 | -41.61 | -0.544 | -0.544 | **> 0,5 %** |
| fe | FE-2TA | TA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0BCC_TA (function, D0 при 298,15 K, без расширения)) | 25 | BCC_B2 1 [BCC_A2] | 0.00626 | 7876.16 | 7960.19 | -84.03 | -1.056 | -1.056 | **> 0,5 %** |
| fe | FE-2TA | TA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0BCC_TA (function, D0 при 298,15 K, без расширения)) | 800 | BCC_B2 1 [BCC_A2] | 0.00626 | 7606.40 | 7690.06 | -83.67 | -1.088 | -1.088 | **> 0,5 %** |
| fe | FE-2TA | TA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0BCC_TA (function, D0 при 298,15 K, без расширения)) | 1000 | FCC_A1 1 | 0.00626 | 7606.59 | 7690.26 | -83.67 | -1.088 | -1.088 | **> 0,5 %** |
| fe | FE-0.1Y | Y (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 25 | FE17Y2 0.00598 [—], H_BCC 0.994 [—] | 0 | — | — | — | — | — |  |
| fe | FE-0.1Y | Y (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 800 | BCC_B2 0.994 [BCC_A2], FE17Y2 0.00578 [—] | 2.17e-05 | — | — | — | — | — |  |
| fe | FE-0.1Y | Y (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 1000 | FCC_A1 0.996, FE17Y2 0.00392 [—] | 0.000217 | — | — | — | — | — |  |
| fe | FE-0.5Y | Y (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 25 | FE17Y2 0.03 [—], H_BCC 0.97 [—] | 0 | — | — | — | — | — |  |
| fe | FE-0.5Y | Y (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 800 | BCC_B2 0.97 [BCC_A2], FE17Y2 0.0298 [—] | 2.12e-05 | — | — | — | — | — |  |
| fe | FE-0.5Y | Y (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 1000 | FCC_A1 0.972, FE17Y2 0.028 [—] | 0.000212 | — | — | — | — | — |  |
| fe | FE-1Y | Y (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 25 | FE17Y2 0.06 [—], H_BCC 0.94 [—] | 0 | — | — | — | — | — |  |
| fe | FE-1Y | Y (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 800 | BCC_B2 0.94 [BCC_A2], FE17Y2 0.0599 [—] | 2.05e-05 | — | — | — | — | — |  |
| fe | FE-1Y | Y (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 1000 | FCC_A1 0.942, FE17Y2 0.0581 [—] | 0.000205 | — | — | — | — | — |  |
| fe | FE-2Y | Y (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 25 | FE17Y2 0.121 [—], H_BCC 0.879 [—] | 0 | — | — | — | — | — |  |
| fe | FE-2Y | Y (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 800 | BCC_B2 0.88 [BCC_A2], FE17Y2 0.12 [—] | 1.92e-05 | — | — | — | — | — |  |
| fe | FE-2Y | Y (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 1000 | FCC_A1 0.881, FE17Y2 0.119 [—] | 0.000192 | — | — | — | — | — |  |
| ni | NI-0.1HF | HF (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 25 | FCC_A1 0.998, NI5HF 0.00197 [—] | 9.98e-15 | — | — | — | — | — |  |
| ni | NI-0.1HF | HF (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 800 | FCC_A1 0.999, NI5HF 0.00121 [—] | 0.000127 | — | — | — | — | — |  |
| ni | NI-0.1HF | HF (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 1000 | FCC_A1 1 | 0.000329 | 8477.66 | 8481.71 | -4.05 | -0.048 | -0.048 |  |
| ni | NI-0.5HF | HF (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 25 | FCC_A1 0.99, NI5HF 0.0099 [—] | 9.9e-15 | — | — | — | — | — |  |
| ni | NI-0.5HF | HF (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 800 | FCC_A1 0.991, NI5HF 0.00914 [—] | 0.000126 | — | — | — | — | — |  |
| ni | NI-0.5HF | HF (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 1000 | FCC_A1 0.997, NI5HF 0.00324 [—] | 0.00111 | — | — | — | — | — |  |
| ni | NI-1HF | HF (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 25 | FCC_A1 0.98, NI5HF 0.0199 [—] | 9.8e-15 | — | — | — | — | — |  |
| ni | NI-1HF | HF (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 800 | FCC_A1 0.981, NI5HF 0.0191 [—] | 0.000125 | — | — | — | — | — |  |
| ni | NI-1HF | HF (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 1000 | FCC_A1 0.987, NI5HF 0.0133 [—] | 0.0011 | — | — | — | — | — |  |
| ni | NI-2HF | HF (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 25 | FCC_A1 0.96, NI5HF 0.04 [—] | 9.6e-15 | — | — | — | — | — |  |
| ni | NI-2HF | HF (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 800 | FCC_A1 0.961, NI5HF 0.0393 [—] | 0.000122 | — | — | — | — | — |  |
| ni | NI-2HF | HF (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 1000 | FCC_A1 0.966, NI5HF 0.0335 [—] | 0.00108 | — | — | — | — | — |  |
| ni | NI-0.1LA | LA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_LA (function, D0 при 298,15 K, без расширения)) | 25 | FCC_A1 0.998, LIQUID 0.00166 | 0.000423 | 8909.27 | 8905.97 | 3.30 | +0.037 | +0.037 |  |
| ni | NI-0.1LA | LA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_LA (function, D0 при 298,15 K, без расширения)) | 800 | FCC_A1 0.998, LIQUID 0.00234 | 0.000423 | 8575.87 | 8573.56 | 2.31 | +0.027 | +0.027 |  |
| ni | NI-0.1LA | LA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_LA (function, D0 при 298,15 K, без расширения)) | 1000 | FCC_A1 0.997, LIQUID 0.0028 | 0.000423 | 8477.57 | 8475.52 | 2.05 | +0.024 | +0.024 |  |
| ni | NI-0.5LA | LA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_LA (function, D0 при 298,15 K, без расширения)) | 25 | FCC_A1 0.992, LIQUID 0.00833 | 0.00212 | 8908.57 | 8892.07 | 16.50 | +0.186 | +0.186 | > 0,1 % |
| ni | NI-0.5LA | LA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_LA (function, D0 при 298,15 K, без расширения)) | 800 | FCC_A1 0.988, LIQUID 0.0118 | 0.00212 | 8572.44 | 8560.91 | 11.53 | +0.135 | +0.135 | > 0,1 % |
| ni | NI-0.5LA | LA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_LA (function, D0 при 298,15 K, без расширения)) | 1000 | FCC_A1 0.986, LIQUID 0.0141 | 0.00212 | 8473.32 | 8463.10 | 10.22 | +0.121 | +0.121 | > 0,1 % |
| ni | NI-1LA | LA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_LA (function, D0 при 298,15 K, без расширения)) | 25 | FCC_A1 0.983, LIQUID 0.0167 | 0.00425 | 8907.68 | 8874.75 | 32.93 | +0.371 | +0.371 | > 0,1 % |
| ni | NI-1LA | LA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_LA (function, D0 при 298,15 K, без расширения)) | 800 | FCC_A1 0.976, LIQUID 0.0236 | 0.00425 | 8568.15 | 8545.14 | 23.01 | +0.269 | +0.269 | > 0,1 % |
| ni | NI-1LA | LA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_LA (function, D0 при 298,15 K, без расширения)) | 1000 | FCC_A1 0.972, LIQUID 0.0282 | 0.00425 | 8468.01 | 8447.63 | 20.39 | +0.241 | +0.241 | > 0,1 % |
| ni | NI-2LA | LA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_LA (function, D0 при 298,15 K, без расширения)) | 25 | FCC_A1 0.966, LIQUID 0.0336 | 0.00855 | 8905.91 | 8840.32 | 65.58 | +0.742 | +0.742 | **> 0,5 %** |
| ni | NI-2LA | LA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_LA (function, D0 при 298,15 K, без расширения)) | 800 | FCC_A1 0.953, LIQUID 0.0474 | 0.00855 | 8559.59 | 8513.78 | 45.80 | +0.538 | +0.538 | **> 0,5 %** |
| ni | NI-2LA | LA (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: D0FCC_LA (function, D0 при 298,15 K, без расширения)) | 1000 | FCC_A1 0.943, LIQUID 0.0567 | 0.00855 | 8457.42 | 8416.84 | 40.58 | +0.482 | +0.482 | > 0,1 % |
| ni | NI-0.1Y | Y (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 25 | FCC_A1 0.996, NI5Y 0.00396 [—] | 9.96e-15 | — | — | — | — | — |  |
| ni | NI-0.1Y | Y (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 800 | FCC_A1 0.996, NI5Y 0.00396 [—] | 1.41e-08 | — | — | — | — | — |  |
| ni | NI-0.1Y | Y (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 1000 | FCC_A1 0.996, NI5Y 0.00396 [—] | 4.36e-07 | — | — | — | — | — |  |
| ni | NI-0.5Y | Y (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 25 | FCC_A1 0.98, NI5Y 0.0198 [—] | 9.8e-15 | — | — | — | — | — |  |
| ni | NI-0.5Y | Y (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 800 | FCC_A1 0.98, NI5Y 0.0198 [—] | 1.39e-08 | — | — | — | — | — |  |
| ni | NI-0.5Y | Y (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 1000 | FCC_A1 0.98, NI5Y 0.0198 [—] | 4.29e-07 | — | — | — | — | — |  |
| ni | NI-1Y | Y (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 25 | FCC_A1 0.96, NI5Y 0.0397 [—] | 9.6e-15 | — | — | — | — | — |  |
| ni | NI-1Y | Y (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 800 | FCC_A1 0.96, NI5Y 0.0397 [—] | 1.36e-08 | — | — | — | — | — |  |
| ni | NI-1Y | Y (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 1000 | FCC_A1 0.96, NI5Y 0.0397 [—] | 4.2e-07 | — | — | — | — | — |  |
| ni | NI-2Y | Y (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 25 | FCC_A1 0.92, NI5Y 0.0798 [—] | 9.2e-15 | — | — | — | — | — |  |
| ni | NI-2Y | Y (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 800 | FCC_A1 0.92, NI5Y 0.0798 [—] | 1.31e-08 | — | — | — | — | — |  |
| ni | NI-2Y | Y (FCC_A1, BCC_A2, HCP_A3, LIQUID; своя: справочник (CRC), 20…25 °C, константа) | 1000 | FCC_A1 0.92, NI5Y 0.0798 [—] | 4.03e-07 | — | — | — | — | — |  |
| ni | NI-0.1ZR | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)) | 25 | FCC_A1 0.997, GAMMA_PRIME 0.00258 [FCC_A1] | 0.000644 | 8908.61 | 8906.27 | 2.34 | +0.026 | +0.026 |  |
| ni | NI-0.1ZR | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)) | 800 | FCC_A1 1 | 0.000644 | 8575.77 | 8573.89 | 1.88 | +0.022 | +0.022 |  |
| ni | NI-0.1ZR | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)) | 1000 | FCC_A1 1 | 0.000644 | 8477.66 | 8475.89 | 1.77 | +0.021 | +0.021 |  |
| ni | NI-0.5ZR | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)) | 25 | FCC_A1 0.987, GAMMA_PRIME 0.0129 [FCC_A1] | 0.00322 | 8905.25 | 8893.58 | 11.67 | +0.131 | +0.131 | > 0,1 % |
| ni | NI-0.5ZR | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)) | 800 | FCC_A1 1 | 0.00322 | 8571.93 | 8562.55 | 9.38 | +0.110 | +0.110 | > 0,1 % |
| ni | NI-0.5ZR | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)) | 1000 | FCC_A1 1 | 0.00322 | 8473.78 | 8464.94 | 8.84 | +0.104 | +0.104 | > 0,1 % |
| ni | NI-1ZR | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)) | 25 | FCC_A1 0.974, GAMMA_PRIME 0.0258 [FCC_A1] | 0.00646 | 8901.04 | 8877.76 | 23.29 | +0.262 | +0.262 | > 0,1 % |
| ni | NI-1ZR | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)) | 800 | FCC_A1 1 | 0.00646 | 8567.14 | 8548.42 | 18.72 | +0.219 | +0.219 | > 0,1 % |
| ni | NI-1ZR | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)) | 1000 | FCC_A1 1 | 0.00646 | 8468.93 | 8451.29 | 17.63 | +0.209 | +0.209 | > 0,1 % |
| ni | NI-2ZR | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)) | 25 | FCC_A1 0.948, GAMMA_PRIME 0.0519 [FCC_A1] | 0.013 | 8892.65 | 8846.29 | 46.36 | +0.524 | +0.524 | **> 0,5 %** |
| ni | NI-2ZR | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)) | 800 | FCC_A1 1 | 0.013 | 8557.57 | 8520.30 | 37.27 | +0.437 | +0.437 | > 0,1 % |
| ni | NI-2ZR | ZR (FCC_A1, BCC_A2, LIQUID; своя: DP(HCP_A3,ZR:VA) (reference)) | 1000 | FCC_A1 1 | 0.013 | 8459.24 | 8424.12 | 35.12 | +0.417 | +0.417 | > 0,1 % |
