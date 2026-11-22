// optimizer: alkaid CSE for constant matvecs; the modules after `chip_28fba9730991` come from alkaid (LGPL-3.0)
// chipin.space chip lab: generated from chipir/1 design chip_28fba9730991. Do not edit; regenerate.
module chip_28fba9730991 (
  input wire [159:0] x,
  output wire [0:0] y
);
  wire [4:0] i_x_0 = x[4:0];
  wire [4:0] i_x_1 = x[9:5];
  wire [4:0] i_x_2 = x[14:10];
  wire [4:0] i_x_3 = x[19:15];
  wire [4:0] i_x_4 = x[24:20];
  wire [4:0] i_x_5 = x[29:25];
  wire [4:0] i_x_6 = x[34:30];
  wire [4:0] i_x_7 = x[39:35];
  wire [4:0] i_x_8 = x[44:40];
  wire [4:0] i_x_9 = x[49:45];
  wire [4:0] i_x_10 = x[54:50];
  wire [4:0] i_x_11 = x[59:55];
  wire [4:0] i_x_12 = x[64:60];
  wire [4:0] i_x_13 = x[69:65];
  wire [4:0] i_x_14 = x[74:70];
  wire [4:0] i_x_15 = x[79:75];
  wire [4:0] i_x_16 = x[84:80];
  wire [4:0] i_x_17 = x[89:85];
  wire [4:0] i_x_18 = x[94:90];
  wire [4:0] i_x_19 = x[99:95];
  wire [4:0] i_x_20 = x[104:100];
  wire [4:0] i_x_21 = x[109:105];
  wire [4:0] i_x_22 = x[114:110];
  wire [4:0] i_x_23 = x[119:115];
  wire [4:0] i_x_24 = x[124:120];
  wire [4:0] i_x_25 = x[129:125];
  wire [4:0] i_x_26 = x[134:130];
  wire [4:0] i_x_27 = x[139:135];
  wire [4:0] i_x_28 = x[144:140];
  wire [4:0] i_x_29 = x[149:145];
  wire [4:0] i_x_30 = x[154:150];
  wire [4:0] i_x_31 = x[159:155];
  // matvec conv: alkaid CSE shift-add network (28 of 28 rows)
  wire [159:0] mvi_conv = {i_x_31, i_x_30, i_x_29, i_x_28, i_x_27, i_x_26, i_x_25, i_x_24, i_x_23, i_x_22, i_x_21, i_x_20, i_x_19, i_x_18, i_x_17, i_x_16, i_x_15, i_x_14, i_x_13, i_x_12, i_x_11, i_x_10, i_x_9, i_x_8, i_x_7, i_x_6, i_x_5, i_x_4, i_x_3, i_x_2, i_x_1, i_x_0};
  wire [230:0] mvo_conv;
  chip_28fba9730991_mv_conv u_chip_28fba9730991_mv_conv (.model_inp(mvi_conv), .model_out(mvo_conv));
  wire [7:0] mvs_conv_0 = mvo_conv[7:0];
  wire [7:0] n_conv_0 = mvs_conv_0;
  wire [7:0] mvs_conv_1 = mvo_conv[15:8];
  wire [7:0] n_conv_1 = mvs_conv_1;
  wire [7:0] mvs_conv_2 = mvo_conv[23:16];
  wire [7:0] n_conv_2 = mvs_conv_2;
  wire [7:0] mvs_conv_3 = mvo_conv[31:24];
  wire [7:0] n_conv_3 = mvs_conv_3;
  wire [7:0] mvs_conv_4 = mvo_conv[39:32];
  wire [7:0] n_conv_4 = mvs_conv_4;
  wire [7:0] mvs_conv_5 = mvo_conv[47:40];
  wire [7:0] n_conv_5 = mvs_conv_5;
  wire [7:0] mvs_conv_6 = mvo_conv[55:48];
  wire [7:0] n_conv_6 = mvs_conv_6;
  wire [8:0] mvs_conv_7 = mvo_conv[64:56];
  wire [8:0] n_conv_7 = mvs_conv_7;
  wire [8:0] mvs_conv_8 = mvo_conv[73:65];
  wire [8:0] n_conv_8 = mvs_conv_8;
  wire [8:0] mvs_conv_9 = mvo_conv[82:74];
  wire [8:0] n_conv_9 = mvs_conv_9;
  wire [8:0] mvs_conv_10 = mvo_conv[91:83];
  wire [8:0] n_conv_10 = mvs_conv_10;
  wire [8:0] mvs_conv_11 = mvo_conv[100:92];
  wire [8:0] n_conv_11 = mvs_conv_11;
  wire [8:0] mvs_conv_12 = mvo_conv[109:101];
  wire [8:0] n_conv_12 = mvs_conv_12;
  wire [8:0] mvs_conv_13 = mvo_conv[118:110];
  wire [8:0] n_conv_13 = mvs_conv_13;
  wire [7:0] mvs_conv_14 = mvo_conv[126:119];
  wire [7:0] n_conv_14 = mvs_conv_14;
  wire [7:0] mvs_conv_15 = mvo_conv[134:127];
  wire [7:0] n_conv_15 = mvs_conv_15;
  wire [7:0] mvs_conv_16 = mvo_conv[142:135];
  wire [7:0] n_conv_16 = mvs_conv_16;
  wire [7:0] mvs_conv_17 = mvo_conv[150:143];
  wire [7:0] n_conv_17 = mvs_conv_17;
  wire [7:0] mvs_conv_18 = mvo_conv[158:151];
  wire [7:0] n_conv_18 = mvs_conv_18;
  wire [7:0] mvs_conv_19 = mvo_conv[166:159];
  wire [7:0] n_conv_19 = mvs_conv_19;
  wire [7:0] mvs_conv_20 = mvo_conv[174:167];
  wire [7:0] n_conv_20 = mvs_conv_20;
  wire [7:0] mvs_conv_21 = mvo_conv[182:175];
  wire [7:0] n_conv_21 = mvs_conv_21;
  wire [7:0] mvs_conv_22 = mvo_conv[190:183];
  wire [7:0] n_conv_22 = mvs_conv_22;
  wire [7:0] mvs_conv_23 = mvo_conv[198:191];
  wire [7:0] n_conv_23 = mvs_conv_23;
  wire [7:0] mvs_conv_24 = mvo_conv[206:199];
  wire [7:0] n_conv_24 = mvs_conv_24;
  wire [7:0] mvs_conv_25 = mvo_conv[214:207];
  wire [7:0] n_conv_25 = mvs_conv_25;
  wire [7:0] mvs_conv_26 = mvo_conv[222:215];
  wire [7:0] n_conv_26 = mvs_conv_26;
  wire [7:0] mvs_conv_27 = mvo_conv[230:223];
  wire [7:0] n_conv_27 = mvs_conv_27;
  wire [3:0] n_conv_sh_0 = n_conv_0[7:4];
  wire [3:0] n_conv_sh_1 = n_conv_1[7:4];
  wire [3:0] n_conv_sh_2 = n_conv_2[7:4];
  wire [3:0] n_conv_sh_3 = n_conv_3[7:4];
  wire [3:0] n_conv_sh_4 = n_conv_4[7:4];
  wire [3:0] n_conv_sh_5 = n_conv_5[7:4];
  wire [3:0] n_conv_sh_6 = n_conv_6[7:4];
  wire [4:0] n_conv_sh_7 = n_conv_7[8:4];
  wire [4:0] n_conv_sh_8 = n_conv_8[8:4];
  wire [4:0] n_conv_sh_9 = n_conv_9[8:4];
  wire [4:0] n_conv_sh_10 = n_conv_10[8:4];
  wire [4:0] n_conv_sh_11 = n_conv_11[8:4];
  wire [4:0] n_conv_sh_12 = n_conv_12[8:4];
  wire [4:0] n_conv_sh_13 = n_conv_13[8:4];
  wire [3:0] n_conv_sh_14 = n_conv_14[7:4];
  wire [3:0] n_conv_sh_15 = n_conv_15[7:4];
  wire [3:0] n_conv_sh_16 = n_conv_16[7:4];
  wire [3:0] n_conv_sh_17 = n_conv_17[7:4];
  wire [3:0] n_conv_sh_18 = n_conv_18[7:4];
  wire [3:0] n_conv_sh_19 = n_conv_19[7:4];
  wire [3:0] n_conv_sh_20 = n_conv_20[7:4];
  wire [3:0] n_conv_sh_21 = n_conv_21[7:4];
  wire [3:0] n_conv_sh_22 = n_conv_22[7:4];
  wire [3:0] n_conv_sh_23 = n_conv_23[7:4];
  wire [3:0] n_conv_sh_24 = n_conv_24[7:4];
  wire [3:0] n_conv_sh_25 = n_conv_25[7:4];
  wire [3:0] n_conv_sh_26 = n_conv_26[7:4];
  wire [3:0] n_conv_sh_27 = n_conv_27[7:4];
  wire [2:0] n_relu_0 = ($signed({{2{n_conv_sh_0[3]}}, n_conv_sh_0}) < $signed(6'd0)) ? 3'd0 : ($signed({{2{n_conv_sh_0[3]}}, n_conv_sh_0}) > $signed(6'd15)) ? 3'd7 : n_conv_sh_0[2:0];
  wire [2:0] n_relu_1 = ($signed({{2{n_conv_sh_1[3]}}, n_conv_sh_1}) < $signed(6'd0)) ? 3'd0 : ($signed({{2{n_conv_sh_1[3]}}, n_conv_sh_1}) > $signed(6'd15)) ? 3'd7 : n_conv_sh_1[2:0];
  wire [2:0] n_relu_2 = ($signed({{2{n_conv_sh_2[3]}}, n_conv_sh_2}) < $signed(6'd0)) ? 3'd0 : ($signed({{2{n_conv_sh_2[3]}}, n_conv_sh_2}) > $signed(6'd15)) ? 3'd7 : n_conv_sh_2[2:0];
  wire [2:0] n_relu_3 = ($signed({{2{n_conv_sh_3[3]}}, n_conv_sh_3}) < $signed(6'd0)) ? 3'd0 : ($signed({{2{n_conv_sh_3[3]}}, n_conv_sh_3}) > $signed(6'd15)) ? 3'd7 : n_conv_sh_3[2:0];
  wire [2:0] n_relu_4 = ($signed({{2{n_conv_sh_4[3]}}, n_conv_sh_4}) < $signed(6'd0)) ? 3'd0 : ($signed({{2{n_conv_sh_4[3]}}, n_conv_sh_4}) > $signed(6'd15)) ? 3'd7 : n_conv_sh_4[2:0];
  wire [2:0] n_relu_5 = ($signed({{2{n_conv_sh_5[3]}}, n_conv_sh_5}) < $signed(6'd0)) ? 3'd0 : ($signed({{2{n_conv_sh_5[3]}}, n_conv_sh_5}) > $signed(6'd15)) ? 3'd7 : n_conv_sh_5[2:0];
  wire [2:0] n_relu_6 = ($signed({{2{n_conv_sh_6[3]}}, n_conv_sh_6}) < $signed(6'd0)) ? 3'd0 : ($signed({{2{n_conv_sh_6[3]}}, n_conv_sh_6}) > $signed(6'd15)) ? 3'd7 : n_conv_sh_6[2:0];
  wire [1:0] n_relu_7 = ($signed({{1{n_conv_sh_7[4]}}, n_conv_sh_7}) < $signed(6'd0)) ? 2'd0 : ($signed({{1{n_conv_sh_7[4]}}, n_conv_sh_7}) > $signed(6'd15)) ? 2'd3 : n_conv_sh_7[1:0];
  wire [1:0] n_relu_8 = ($signed({{1{n_conv_sh_8[4]}}, n_conv_sh_8}) < $signed(6'd0)) ? 2'd0 : ($signed({{1{n_conv_sh_8[4]}}, n_conv_sh_8}) > $signed(6'd15)) ? 2'd3 : n_conv_sh_8[1:0];
  wire [1:0] n_relu_9 = ($signed({{1{n_conv_sh_9[4]}}, n_conv_sh_9}) < $signed(6'd0)) ? 2'd0 : ($signed({{1{n_conv_sh_9[4]}}, n_conv_sh_9}) > $signed(6'd15)) ? 2'd3 : n_conv_sh_9[1:0];
  wire [1:0] n_relu_10 = ($signed({{1{n_conv_sh_10[4]}}, n_conv_sh_10}) < $signed(6'd0)) ? 2'd0 : ($signed({{1{n_conv_sh_10[4]}}, n_conv_sh_10}) > $signed(6'd15)) ? 2'd3 : n_conv_sh_10[1:0];
  wire [1:0] n_relu_11 = ($signed({{1{n_conv_sh_11[4]}}, n_conv_sh_11}) < $signed(6'd0)) ? 2'd0 : ($signed({{1{n_conv_sh_11[4]}}, n_conv_sh_11}) > $signed(6'd15)) ? 2'd3 : n_conv_sh_11[1:0];
  wire [1:0] n_relu_12 = ($signed({{1{n_conv_sh_12[4]}}, n_conv_sh_12}) < $signed(6'd0)) ? 2'd0 : ($signed({{1{n_conv_sh_12[4]}}, n_conv_sh_12}) > $signed(6'd15)) ? 2'd3 : n_conv_sh_12[1:0];
  wire [1:0] n_relu_13 = ($signed({{1{n_conv_sh_13[4]}}, n_conv_sh_13}) < $signed(6'd0)) ? 2'd0 : ($signed({{1{n_conv_sh_13[4]}}, n_conv_sh_13}) > $signed(6'd15)) ? 2'd3 : n_conv_sh_13[1:0];
  wire [2:0] n_relu_14 = ($signed({{2{n_conv_sh_14[3]}}, n_conv_sh_14}) < $signed(6'd0)) ? 3'd0 : ($signed({{2{n_conv_sh_14[3]}}, n_conv_sh_14}) > $signed(6'd15)) ? 3'd7 : n_conv_sh_14[2:0];
  wire [2:0] n_relu_15 = ($signed({{2{n_conv_sh_15[3]}}, n_conv_sh_15}) < $signed(6'd0)) ? 3'd0 : ($signed({{2{n_conv_sh_15[3]}}, n_conv_sh_15}) > $signed(6'd15)) ? 3'd7 : n_conv_sh_15[2:0];
  wire [2:0] n_relu_16 = ($signed({{2{n_conv_sh_16[3]}}, n_conv_sh_16}) < $signed(6'd0)) ? 3'd0 : ($signed({{2{n_conv_sh_16[3]}}, n_conv_sh_16}) > $signed(6'd15)) ? 3'd7 : n_conv_sh_16[2:0];
  wire [2:0] n_relu_17 = ($signed({{2{n_conv_sh_17[3]}}, n_conv_sh_17}) < $signed(6'd0)) ? 3'd0 : ($signed({{2{n_conv_sh_17[3]}}, n_conv_sh_17}) > $signed(6'd15)) ? 3'd7 : n_conv_sh_17[2:0];
  wire [2:0] n_relu_18 = ($signed({{2{n_conv_sh_18[3]}}, n_conv_sh_18}) < $signed(6'd0)) ? 3'd0 : ($signed({{2{n_conv_sh_18[3]}}, n_conv_sh_18}) > $signed(6'd15)) ? 3'd7 : n_conv_sh_18[2:0];
  wire [2:0] n_relu_19 = ($signed({{2{n_conv_sh_19[3]}}, n_conv_sh_19}) < $signed(6'd0)) ? 3'd0 : ($signed({{2{n_conv_sh_19[3]}}, n_conv_sh_19}) > $signed(6'd15)) ? 3'd7 : n_conv_sh_19[2:0];
  wire [2:0] n_relu_20 = ($signed({{2{n_conv_sh_20[3]}}, n_conv_sh_20}) < $signed(6'd0)) ? 3'd0 : ($signed({{2{n_conv_sh_20[3]}}, n_conv_sh_20}) > $signed(6'd15)) ? 3'd7 : n_conv_sh_20[2:0];
  wire [2:0] n_relu_21 = ($signed({{2{n_conv_sh_21[3]}}, n_conv_sh_21}) < $signed(6'd0)) ? 3'd0 : ($signed({{2{n_conv_sh_21[3]}}, n_conv_sh_21}) > $signed(6'd15)) ? 3'd7 : n_conv_sh_21[2:0];
  wire [2:0] n_relu_22 = ($signed({{2{n_conv_sh_22[3]}}, n_conv_sh_22}) < $signed(6'd0)) ? 3'd0 : ($signed({{2{n_conv_sh_22[3]}}, n_conv_sh_22}) > $signed(6'd15)) ? 3'd7 : n_conv_sh_22[2:0];
  wire [2:0] n_relu_23 = ($signed({{2{n_conv_sh_23[3]}}, n_conv_sh_23}) < $signed(6'd0)) ? 3'd0 : ($signed({{2{n_conv_sh_23[3]}}, n_conv_sh_23}) > $signed(6'd15)) ? 3'd7 : n_conv_sh_23[2:0];
  wire [2:0] n_relu_24 = ($signed({{2{n_conv_sh_24[3]}}, n_conv_sh_24}) < $signed(6'd0)) ? 3'd0 : ($signed({{2{n_conv_sh_24[3]}}, n_conv_sh_24}) > $signed(6'd15)) ? 3'd7 : n_conv_sh_24[2:0];
  wire [2:0] n_relu_25 = ($signed({{2{n_conv_sh_25[3]}}, n_conv_sh_25}) < $signed(6'd0)) ? 3'd0 : ($signed({{2{n_conv_sh_25[3]}}, n_conv_sh_25}) > $signed(6'd15)) ? 3'd7 : n_conv_sh_25[2:0];
  wire [2:0] n_relu_26 = ($signed({{2{n_conv_sh_26[3]}}, n_conv_sh_26}) < $signed(6'd0)) ? 3'd0 : ($signed({{2{n_conv_sh_26[3]}}, n_conv_sh_26}) > $signed(6'd15)) ? 3'd7 : n_conv_sh_26[2:0];
  wire [2:0] n_relu_27 = ($signed({{2{n_conv_sh_27[3]}}, n_conv_sh_27}) < $signed(6'd0)) ? 3'd0 : ($signed({{2{n_conv_sh_27[3]}}, n_conv_sh_27}) > $signed(6'd15)) ? 3'd7 : n_conv_sh_27[2:0];
  wire [4:0] n_pool_0_t1 = {{2{1'b0}}, n_relu_0};
  wire [4:0] n_pool_0_t2 = ($signed({{2{1'b0}}, n_relu_1}) > $signed(n_pool_0_t1)) ? {{2{1'b0}}, n_relu_1} : n_pool_0_t1;
  wire [4:0] n_pool_0_t3 = ($signed({{2{1'b0}}, n_relu_2}) > $signed(n_pool_0_t2)) ? {{2{1'b0}}, n_relu_2} : n_pool_0_t2;
  wire [4:0] n_pool_0_t4 = ($signed({{2{1'b0}}, n_relu_3}) > $signed(n_pool_0_t3)) ? {{2{1'b0}}, n_relu_3} : n_pool_0_t3;
  wire [4:0] n_pool_0_t5 = ($signed({{2{1'b0}}, n_relu_4}) > $signed(n_pool_0_t4)) ? {{2{1'b0}}, n_relu_4} : n_pool_0_t4;
  wire [4:0] n_pool_0_t6 = ($signed({{2{1'b0}}, n_relu_5}) > $signed(n_pool_0_t5)) ? {{2{1'b0}}, n_relu_5} : n_pool_0_t5;
  wire [4:0] n_pool_0_t7 = ($signed({{2{1'b0}}, n_relu_6}) > $signed(n_pool_0_t6)) ? {{2{1'b0}}, n_relu_6} : n_pool_0_t6;
  wire [2:0] n_pool_0 = n_pool_0_t7[2:0];
  wire [3:0] n_pool_1_t8 = {{2{1'b0}}, n_relu_7};
  wire [3:0] n_pool_1_t9 = ($signed({{2{1'b0}}, n_relu_8}) > $signed(n_pool_1_t8)) ? {{2{1'b0}}, n_relu_8} : n_pool_1_t8;
  wire [3:0] n_pool_1_t10 = ($signed({{2{1'b0}}, n_relu_9}) > $signed(n_pool_1_t9)) ? {{2{1'b0}}, n_relu_9} : n_pool_1_t9;
  wire [3:0] n_pool_1_t11 = ($signed({{2{1'b0}}, n_relu_10}) > $signed(n_pool_1_t10)) ? {{2{1'b0}}, n_relu_10} : n_pool_1_t10;
  wire [3:0] n_pool_1_t12 = ($signed({{2{1'b0}}, n_relu_11}) > $signed(n_pool_1_t11)) ? {{2{1'b0}}, n_relu_11} : n_pool_1_t11;
  wire [3:0] n_pool_1_t13 = ($signed({{2{1'b0}}, n_relu_12}) > $signed(n_pool_1_t12)) ? {{2{1'b0}}, n_relu_12} : n_pool_1_t12;
  wire [3:0] n_pool_1_t14 = ($signed({{2{1'b0}}, n_relu_13}) > $signed(n_pool_1_t13)) ? {{2{1'b0}}, n_relu_13} : n_pool_1_t13;
  wire [1:0] n_pool_1 = n_pool_1_t14[1:0];
  wire [4:0] n_pool_2_t15 = {{2{1'b0}}, n_relu_14};
  wire [4:0] n_pool_2_t16 = ($signed({{2{1'b0}}, n_relu_15}) > $signed(n_pool_2_t15)) ? {{2{1'b0}}, n_relu_15} : n_pool_2_t15;
  wire [4:0] n_pool_2_t17 = ($signed({{2{1'b0}}, n_relu_16}) > $signed(n_pool_2_t16)) ? {{2{1'b0}}, n_relu_16} : n_pool_2_t16;
  wire [4:0] n_pool_2_t18 = ($signed({{2{1'b0}}, n_relu_17}) > $signed(n_pool_2_t17)) ? {{2{1'b0}}, n_relu_17} : n_pool_2_t17;
  wire [4:0] n_pool_2_t19 = ($signed({{2{1'b0}}, n_relu_18}) > $signed(n_pool_2_t18)) ? {{2{1'b0}}, n_relu_18} : n_pool_2_t18;
  wire [4:0] n_pool_2_t20 = ($signed({{2{1'b0}}, n_relu_19}) > $signed(n_pool_2_t19)) ? {{2{1'b0}}, n_relu_19} : n_pool_2_t19;
  wire [4:0] n_pool_2_t21 = ($signed({{2{1'b0}}, n_relu_20}) > $signed(n_pool_2_t20)) ? {{2{1'b0}}, n_relu_20} : n_pool_2_t20;
  wire [2:0] n_pool_2 = n_pool_2_t21[2:0];
  wire [4:0] n_pool_3_t22 = {{2{1'b0}}, n_relu_21};
  wire [4:0] n_pool_3_t23 = ($signed({{2{1'b0}}, n_relu_22}) > $signed(n_pool_3_t22)) ? {{2{1'b0}}, n_relu_22} : n_pool_3_t22;
  wire [4:0] n_pool_3_t24 = ($signed({{2{1'b0}}, n_relu_23}) > $signed(n_pool_3_t23)) ? {{2{1'b0}}, n_relu_23} : n_pool_3_t23;
  wire [4:0] n_pool_3_t25 = ($signed({{2{1'b0}}, n_relu_24}) > $signed(n_pool_3_t24)) ? {{2{1'b0}}, n_relu_24} : n_pool_3_t24;
  wire [4:0] n_pool_3_t26 = ($signed({{2{1'b0}}, n_relu_25}) > $signed(n_pool_3_t25)) ? {{2{1'b0}}, n_relu_25} : n_pool_3_t25;
  wire [4:0] n_pool_3_t27 = ($signed({{2{1'b0}}, n_relu_26}) > $signed(n_pool_3_t26)) ? {{2{1'b0}}, n_relu_26} : n_pool_3_t26;
  wire [4:0] n_pool_3_t28 = ($signed({{2{1'b0}}, n_relu_27}) > $signed(n_pool_3_t27)) ? {{2{1'b0}}, n_relu_27} : n_pool_3_t27;
  wire [2:0] n_pool_3 = n_pool_3_t28[2:0];
  // matvec score: alkaid CSE shift-add network (1 of 1 rows)
  wire [10:0] mvi_score = {n_pool_3, n_pool_2, n_pool_1, n_pool_0};
  wire [6:0] mvo_score;
  chip_28fba9730991_mv_score u_chip_28fba9730991_mv_score (.model_inp(mvi_score), .model_out(mvo_score));
  wire [6:0] mvs_score_0 = mvo_score[6:0];
  wire [6:0] n_score_0 = mvs_score_0;
  wire [0:0] n_dec_0 = ($signed({{1{n_score_0[6]}}, n_score_0}) > $signed(8'd0)) ? 1'b1 : 1'b0;
  assign y = n_dec_0;
endmodule

module chip_28fba9730991_mv_conv (
    input [159:0] model_inp,
    output [230:0] model_out
);

    // verilator lint_off UNUSEDSIGNAL
    // Explicit quantization operation will drop bits if exists

    wire [4:0] v0; assign v0[4:0] = model_inp[9:5];
    wire [4:0] v1; assign v1[4:0] = model_inp[84:80];
    wire [4:0] v2; assign v2[4:0] = model_inp[89:85];
    wire [5:0] v3; chipin_alk_shift_adder #(5,5,0,0,6,0,0,1) op_3 (v1[4:0],v2[4:0],v3[5:0]);
    wire [4:0] v4; assign v4[4:0] = model_inp[154:150];
    wire [4:0] v5; assign v5[4:0] = model_inp[4:0];
    wire [4:0] v6; assign v6[4:0] = model_inp[74:70];
    wire [4:0] v7; assign v7[4:0] = model_inp[79:75];
    wire [4:0] v8; assign v8[4:0] = model_inp[94:90];
    wire [4:0] v9; assign v9[4:0] = model_inp[99:95];
    wire [5:0] v10; chipin_alk_shift_adder #(5,5,0,0,6,0,0,1) op_10 (v8[4:0],v9[4:0],v10[5:0]);
    wire [4:0] v11; assign v11[4:0] = model_inp[104:100];
    wire [4:0] v12; assign v12[4:0] = model_inp[109:105];
    wire [5:0] v13; chipin_alk_shift_adder #(5,5,0,0,6,0,0,1) op_13 (v11[4:0],v12[4:0],v13[5:0]);
    wire [4:0] v14; assign v14[4:0] = model_inp[114:110];
    wire [4:0] v15; assign v15[4:0] = model_inp[119:115];
    wire [5:0] v16; chipin_alk_shift_adder #(5,5,0,0,6,0,0,1) op_16 (v14[4:0],v15[4:0],v16[5:0]);
    wire [4:0] v17; assign v17[4:0] = model_inp[124:120];
    wire [4:0] v18; assign v18[4:0] = model_inp[129:125];
    wire [5:0] v19; chipin_alk_shift_adder #(5,5,0,0,6,0,0,1) op_19 (v17[4:0],v18[4:0],v19[5:0]);
    wire [4:0] v20; assign v20[4:0] = model_inp[134:130];
    wire [4:0] v21; assign v21[4:0] = model_inp[139:135];
    wire [5:0] v22; chipin_alk_shift_adder #(5,5,0,0,6,0,0,1) op_22 (v20[4:0],v21[4:0],v22[5:0]);
    wire [4:0] v23; assign v23[4:0] = model_inp[144:140];
    wire [4:0] v24; assign v24[4:0] = model_inp[149:145];
    wire [5:0] v25; chipin_alk_shift_adder #(5,5,0,0,6,0,0,1) op_25 (v23[4:0],v24[4:0],v25[5:0]);
    wire [6:0] v26; chipin_alk_shift_adder #(5,6,0,1,7,0,0,0) op_26 (v6[4:0],v25[5:0],v26[6:0]);
    wire [7:0] v27; chipin_alk_shift_adder #(7,5,1,0,8,0,0,0) op_27 (v26[6:0],5'b10011,v27[7:0]);
    wire [6:0] v28; chipin_alk_shift_adder #(5,6,0,1,7,0,0,0) op_28 (v4[4:0],v25[5:0],v28[6:0]);
    wire [6:0] v29; chipin_alk_shift_adder #(5,7,0,1,7,0,0,1) op_29 (v7[4:0],v28[6:0],v29[6:0]);
    wire [4:0] v30; assign v30[4:0] = model_inp[159:155];
    wire [7:0] v31; chipin_alk_ternary_adder #(5,0,1,0,5,0,1,0,7,1,0,0,8,0) op_31 (v30[4:0],v6[4:0],v29[6:0],v31[7:0]);
    wire [8:0] v32; chipin_alk_shift_adder #(8,1,1,0,9,0,4,1) op_32 (v31[7:0],1'b1,v32[8:0]);
    wire [4:0] v33; assign v33[4:0] = model_inp[19:15];
    wire [6:0] v34; chipin_alk_ternary_adder #(5,0,1,0,6,1,1,0,5,0,0,0,7,0) op_34 (v8[4:0],v3[5:0],v33[4:0],v34[6:0]);
    wire [7:0] v35; chipin_alk_ternary_adder #(5,0,0,0,5,0,1,0,7,1,0,0,8,0) op_35 (v0[4:0],v5[4:0],v34[6:0],v35[7:0]);
    wire [7:0] v36; chipin_alk_shift_adder #(8,3,1,0,8,0,0,0) op_36 (v35[7:0],3'b111,v36[7:0]);
    wire [5:0] v37; chipin_alk_shift_adder #(5,5,0,0,6,0,0,0) op_37 (v5[4:0],v33[4:0],v37[5:0]);
    wire [7:0] v38; chipin_alk_ternary_adder #(6,1,0,0,6,1,0,0,6,0,0,0,8,0) op_38 (v10[5:0],v3[5:0],v37[5:0],v38[7:0]);
    wire [4:0] v39; assign v39[4:0] = model_inp[29:25];
    wire [6:0] v40; chipin_alk_ternary_adder #(5,0,1,0,6,1,1,0,5,0,0,0,7,0) op_40 (v11[4:0],v10[5:0],v39[4:0],v40[6:0]);
    wire [4:0] v41; assign v41[4:0] = model_inp[39:35];
    wire [6:0] v42; chipin_alk_ternary_adder #(5,0,1,0,6,1,1,0,5,0,0,0,7,0) op_42 (v14[4:0],v13[5:0],v41[4:0],v42[6:0]);
    wire [4:0] v43; assign v43[4:0] = model_inp[49:45];
    wire [6:0] v44; chipin_alk_ternary_adder #(5,0,1,0,6,1,1,0,5,0,0,0,7,0) op_44 (v17[4:0],v16[5:0],v43[4:0],v44[6:0]);
    wire [4:0] v45; assign v45[4:0] = model_inp[59:55];
    wire [6:0] v46; chipin_alk_ternary_adder #(5,0,1,0,6,1,1,0,5,0,0,0,7,0) op_46 (v20[4:0],v19[5:0],v45[4:0],v46[6:0]);
    wire [4:0] v47; assign v47[4:0] = model_inp[69:65];
    wire [6:0] v48; chipin_alk_ternary_adder #(5,0,1,0,6,1,1,0,5,0,0,0,7,0) op_48 (v23[4:0],v22[5:0],v47[4:0],v48[6:0]);
    wire [4:0] v49; assign v49[4:0] = model_inp[14:10];
    wire [6:0] v50; chipin_alk_shift_adder #(5,6,0,1,7,0,0,0) op_50 (v49[4:0],v3[5:0],v50[6:0]);
    wire [7:0] v51; chipin_alk_shift_adder #(7,5,1,0,8,0,0,0) op_51 (v50[6:0],5'b10011,v51[7:0]);
    wire [7:0] v52; chipin_alk_ternary_adder #(5,0,1,0,5,0,1,0,7,1,0,0,8,0) op_52 (v9[4:0],v49[4:0],v34[6:0],v52[7:0]);
    wire [8:0] v53; chipin_alk_shift_adder #(8,1,1,0,9,0,4,1) op_53 (v52[7:0],1'b1,v53[8:0]);
    wire [5:0] v54; chipin_alk_shift_adder #(5,5,0,0,6,0,0,0) op_54 (v49[4:0],v39[4:0],v54[5:0]);
    wire [7:0] v55; chipin_alk_ternary_adder #(6,1,0,0,6,1,0,0,6,0,0,0,8,0) op_55 (v13[5:0],v10[5:0],v54[5:0],v55[7:0]);
    wire [7:0] v56; chipin_alk_ternary_adder #(5,0,0,0,5,0,1,0,7,1,0,0,8,0) op_56 (v33[4:0],v49[4:0],v40[6:0],v56[7:0]);
    wire [7:0] v57; chipin_alk_shift_adder #(8,3,1,0,8,0,0,0) op_57 (v56[7:0],3'b111,v57[7:0]);
    wire [4:0] v58; assign v58[4:0] = model_inp[24:20];
    wire [6:0] v59; chipin_alk_shift_adder #(5,6,0,1,7,0,0,0) op_59 (v58[4:0],v10[5:0],v59[6:0]);
    wire [7:0] v60; chipin_alk_shift_adder #(7,5,1,0,8,0,0,0) op_60 (v59[6:0],5'b10011,v60[7:0]);
    wire [7:0] v61; chipin_alk_ternary_adder #(5,0,1,0,5,0,1,0,7,1,0,0,8,0) op_61 (v12[4:0],v58[4:0],v40[6:0],v61[7:0]);
    wire [8:0] v62; chipin_alk_shift_adder #(8,1,1,0,9,0,4,1) op_62 (v61[7:0],1'b1,v62[8:0]);
    wire [5:0] v63; chipin_alk_shift_adder #(5,5,0,0,6,0,0,0) op_63 (v58[4:0],v41[4:0],v63[5:0]);
    wire [7:0] v64; chipin_alk_ternary_adder #(6,1,0,0,6,1,0,0,6,0,0,0,8,0) op_64 (v16[5:0],v13[5:0],v63[5:0],v64[7:0]);
    wire [7:0] v65; chipin_alk_ternary_adder #(5,0,0,0,5,0,1,0,7,1,0,0,8,0) op_65 (v39[4:0],v58[4:0],v42[6:0],v65[7:0]);
    wire [7:0] v66; chipin_alk_shift_adder #(8,3,1,0,8,0,0,0) op_66 (v65[7:0],3'b111,v66[7:0]);
    wire [4:0] v67; assign v67[4:0] = model_inp[34:30];
    wire [6:0] v68; chipin_alk_shift_adder #(5,6,0,1,7,0,0,0) op_68 (v67[4:0],v13[5:0],v68[6:0]);
    wire [7:0] v69; chipin_alk_shift_adder #(7,5,1,0,8,0,0,0) op_69 (v68[6:0],5'b10011,v69[7:0]);
    wire [7:0] v70; chipin_alk_ternary_adder #(5,0,1,0,5,0,1,0,7,1,0,0,8,0) op_70 (v15[4:0],v67[4:0],v42[6:0],v70[7:0]);
    wire [8:0] v71; chipin_alk_shift_adder #(8,1,1,0,9,0,4,1) op_71 (v70[7:0],1'b1,v71[8:0]);
    wire [5:0] v72; chipin_alk_shift_adder #(5,5,0,0,6,0,0,0) op_72 (v67[4:0],v43[4:0],v72[5:0]);
    wire [7:0] v73; chipin_alk_ternary_adder #(6,1,0,0,6,1,0,0,6,0,0,0,8,0) op_73 (v19[5:0],v16[5:0],v72[5:0],v73[7:0]);
    wire [7:0] v74; chipin_alk_ternary_adder #(5,0,0,0,5,0,1,0,7,1,0,0,8,0) op_74 (v41[4:0],v67[4:0],v44[6:0],v74[7:0]);
    wire [7:0] v75; chipin_alk_shift_adder #(8,3,1,0,8,0,0,0) op_75 (v74[7:0],3'b111,v75[7:0]);
    wire [4:0] v76; assign v76[4:0] = model_inp[44:40];
    wire [6:0] v77; chipin_alk_shift_adder #(5,6,0,1,7,0,0,0) op_77 (v76[4:0],v16[5:0],v77[6:0]);
    wire [7:0] v78; chipin_alk_shift_adder #(7,5,1,0,8,0,0,0) op_78 (v77[6:0],5'b10011,v78[7:0]);
    wire [7:0] v79; chipin_alk_ternary_adder #(5,0,1,0,5,0,1,0,7,1,0,0,8,0) op_79 (v18[4:0],v76[4:0],v44[6:0],v79[7:0]);
    wire [8:0] v80; chipin_alk_shift_adder #(8,1,1,0,9,0,4,1) op_80 (v79[7:0],1'b1,v80[8:0]);
    wire [5:0] v81; chipin_alk_shift_adder #(5,5,0,0,6,0,0,0) op_81 (v76[4:0],v45[4:0],v81[5:0]);
    wire [7:0] v82; chipin_alk_ternary_adder #(6,1,0,0,6,1,0,0,6,0,0,0,8,0) op_82 (v22[5:0],v19[5:0],v81[5:0],v82[7:0]);
    wire [7:0] v83; chipin_alk_ternary_adder #(5,0,0,0,5,0,1,0,7,1,0,0,8,0) op_83 (v43[4:0],v76[4:0],v46[6:0],v83[7:0]);
    wire [7:0] v84; chipin_alk_shift_adder #(8,3,1,0,8,0,0,0) op_84 (v83[7:0],3'b111,v84[7:0]);
    wire [4:0] v85; assign v85[4:0] = model_inp[54:50];
    wire [6:0] v86; chipin_alk_shift_adder #(5,6,0,1,7,0,0,0) op_86 (v85[4:0],v19[5:0],v86[6:0]);
    wire [7:0] v87; chipin_alk_shift_adder #(7,5,1,0,8,0,0,0) op_87 (v86[6:0],5'b10011,v87[7:0]);
    wire [7:0] v88; chipin_alk_ternary_adder #(5,0,1,0,5,0,1,0,7,1,0,0,8,0) op_88 (v21[4:0],v85[4:0],v46[6:0],v88[7:0]);
    wire [8:0] v89; chipin_alk_shift_adder #(8,1,1,0,9,0,4,1) op_89 (v88[7:0],1'b1,v89[8:0]);
    wire [5:0] v90; chipin_alk_shift_adder #(5,5,0,0,6,0,0,0) op_90 (v85[4:0],v47[4:0],v90[5:0]);
    wire [7:0] v91; chipin_alk_ternary_adder #(6,1,0,0,6,1,0,0,6,0,0,0,8,0) op_91 (v25[5:0],v22[5:0],v90[5:0],v91[7:0]);
    wire [7:0] v92; chipin_alk_ternary_adder #(5,0,0,0,5,0,1,0,7,1,0,0,8,0) op_92 (v45[4:0],v85[4:0],v48[6:0],v92[7:0]);
    wire [7:0] v93; chipin_alk_shift_adder #(8,3,1,0,8,0,0,0) op_93 (v92[7:0],3'b111,v93[7:0]);
    wire [4:0] v94; assign v94[4:0] = model_inp[64:60];
    wire [6:0] v95; chipin_alk_shift_adder #(5,6,0,1,7,0,0,0) op_95 (v94[4:0],v22[5:0],v95[6:0]);
    wire [7:0] v96; chipin_alk_shift_adder #(7,5,1,0,8,0,0,0) op_96 (v95[6:0],5'b10011,v96[7:0]);
    wire [7:0] v97; chipin_alk_ternary_adder #(5,0,1,0,5,0,1,0,7,1,0,0,8,0) op_97 (v24[4:0],v94[4:0],v48[6:0],v97[7:0]);
    wire [8:0] v98; chipin_alk_shift_adder #(8,1,1,0,9,0,4,1) op_98 (v97[7:0],1'b1,v98[8:0]);
    wire [5:0] v99; chipin_alk_shift_adder #(5,5,0,0,6,0,0,0) op_99 (v94[4:0],v7[4:0],v99[5:0]);
    wire [7:0] v100; chipin_alk_ternary_adder #(6,0,0,0,5,0,1,0,7,1,0,0,8,0) op_100 (v99[5:0],v30[4:0],v28[6:0],v100[7:0]);
    wire [7:0] v101; chipin_alk_ternary_adder #(5,0,0,0,5,0,1,0,7,1,0,0,8,0) op_101 (v47[4:0],v94[4:0],v29[6:0],v101[7:0]);
    wire [7:0] v102; chipin_alk_shift_adder #(8,3,1,0,8,0,0,0) op_102 (v101[7:0],3'b111,v102[7:0]);

    // verilator lint_on UNUSEDSIGNAL

    assign model_out[7:0] = v38[7:0];
    assign model_out[15:8] = v55[7:0];
    assign model_out[23:16] = v64[7:0];
    assign model_out[31:24] = v73[7:0];
    assign model_out[39:32] = v82[7:0];
    assign model_out[47:40] = v91[7:0];
    assign model_out[55:48] = v100[7:0];
    assign model_out[64:56] = v53[8:0];
    assign model_out[73:65] = v62[8:0];
    assign model_out[82:74] = v71[8:0];
    assign model_out[91:83] = v80[8:0];
    assign model_out[100:92] = v89[8:0];
    assign model_out[109:101] = v98[8:0];
    assign model_out[118:110] = v32[8:0];
    assign model_out[126:119] = v51[7:0];
    assign model_out[134:127] = v60[7:0];
    assign model_out[142:135] = v69[7:0];
    assign model_out[150:143] = v78[7:0];
    assign model_out[158:151] = v87[7:0];
    assign model_out[166:159] = v96[7:0];
    assign model_out[174:167] = v27[7:0];
    assign model_out[182:175] = v36[7:0];
    assign model_out[190:183] = v57[7:0];
    assign model_out[198:191] = v66[7:0];
    assign model_out[206:199] = v75[7:0];
    assign model_out[214:207] = v84[7:0];
    assign model_out[222:215] = v93[7:0];
    assign model_out[230:223] = v102[7:0];

endmodule

module chip_28fba9730991_mv_score (
    input [10:0] model_inp,
    output [6:0] model_out
);

    // verilator lint_off UNUSEDSIGNAL
    // Explicit quantization operation will drop bits if exists

    wire [1:0] v0; assign v0[1:0] = model_inp[4:3];
    wire [2:0] v1; assign v1[2:0] = model_inp[2:0];
    wire [2:0] v2; assign v2[2:0] = model_inp[7:5];
    wire [5:0] v3; chipin_alk_shift_adder #(3,2,0,0,6,0,-2,1) op_3 (v2[2:0],v0[1:0],v3[5:0]);
    wire [2:0] v4; assign v4[2:0] = model_inp[10:8];
    wire [3:0] v5; chipin_alk_shift_adder #(3,3,0,0,4,0,0,1) op_5 (v1[2:0],v4[2:0],v5[3:0]);
    wire [6:0] v6; chipin_alk_ternary_adder #(6,1,0,0,4,1,0,2,4,1,1,0,7,0) op_6 (v3[5:0],v5[3:0],v5[3:0],v6[6:0]);
    wire [6:0] v7; chipin_alk_shift_adder #(7,1,1,0,7,0,3,1) op_7 (v6[6:0],1'b1,v7[6:0]);

    // verilator lint_on UNUSEDSIGNAL

    assign model_out[6:0] = v7[6:0];

endmodule




module chipin_alk_shift_adder #(
    parameter BW_INPUT0 = 32,
    parameter BW_INPUT1 = 32,
    parameter SIGNED0 = 0,
    parameter SIGNED1 = 0,
    parameter BW_OUT = 32,
    parameter DROP_LSBS = 0,
    parameter SHIFT1 = 0,
    parameter IS_SUB = 0
) (
    input [BW_INPUT0-1:0] in0,
    input [BW_INPUT1-1:0] in1,
    output [BW_OUT-1:0] out
);

  localparam IN0_NEED_BITS = (SHIFT1 < 0) ? BW_INPUT0 - SHIFT1 : BW_INPUT0;
  localparam IN1_NEED_BITS = (SHIFT1 > 0) ? BW_INPUT1 + SHIFT1 : BW_INPUT1;
  localparam EXTRA_PAD = (SIGNED0 != SIGNED1) ? IS_SUB + 1 : IS_SUB + 0;
  localparam BW_ADD = (IN0_NEED_BITS > IN1_NEED_BITS) ? IN0_NEED_BITS + EXTRA_PAD + 1 : IN1_NEED_BITS + EXTRA_PAD + 1;
  localparam IN0_PAD_LEFT = (SHIFT1 < 0) ? BW_ADD - BW_INPUT0 + SHIFT1 : BW_ADD - BW_INPUT0;
  localparam IN0_PAD_RIGHT = (SHIFT1 < 0) ? -SHIFT1 : 0;
  localparam IN1_PAD_LEFT = (SHIFT1 > 0) ? BW_ADD - BW_INPUT1 - SHIFT1 : BW_ADD - BW_INPUT1;
  localparam IN1_PAD_RIGHT = (SHIFT1 > 0) ? SHIFT1 : 0;

  localparam ABS_SHIFT = (SHIFT1 > 0) ? SHIFT1 : (SHIFT1 < 0) ? -SHIFT1 : 0;

  // verilator lint_off UNUSEDSIGNAL
  wire [BW_ADD-1:0] in0_ext;
  wire [BW_ADD-1:0] in1_ext;
  wire [BW_ADD-1:0] accum;
  // verilator lint_on UNUSEDSIGNAL

  generate
    if (SIGNED0 == 1) begin : in0_is_signed
      assign in0_ext = {{IN0_PAD_LEFT{in0[BW_INPUT0-1]}}, in0, {IN0_PAD_RIGHT{1'b0}}};
    end else begin : in0_is_unsigned
      assign in0_ext = {{IN0_PAD_LEFT{1'b0}}, in0, {IN0_PAD_RIGHT{1'b0}}};
    end
  endgenerate

  generate
    if (SIGNED1 == 1) begin : in1_is_signed
      assign in1_ext = {{IN1_PAD_LEFT{in1[BW_INPUT1-1]}}, in1, {IN1_PAD_RIGHT{1'b0}}};
    end else begin : in1_is_unsigned
      assign in1_ext = {{IN1_PAD_LEFT{1'b0}}, in1, {IN1_PAD_RIGHT{1'b0}}};
    end
  endgenerate

  generate
    if (SHIFT1 == 0) begin : no_shift
      if (IS_SUB == 1) begin : is_sub
        assign accum = in0_ext - in1_ext;
      end else begin : is_add
        assign accum = in0_ext + in1_ext;
      end
    end else if (SHIFT1 > 0) begin : shift_pos
      // copy lower SHIFT1 bits
      assign accum[ABS_SHIFT-1:0] = in0_ext[ABS_SHIFT-1:0];
      // upper bits
      if (ABS_SHIFT >= BW_INPUT0 && SIGNED0 == 0) begin : disjoint
        // in0 unsigned, disjoint
        if (IS_SUB == 0) begin : is_add
          assign accum[BW_ADD-1:ABS_SHIFT] = in1_ext[BW_ADD-1:ABS_SHIFT];
        end else begin : is_sub
          assign accum[BW_ADD-1:ABS_SHIFT] = -in1_ext[BW_ADD-1:ABS_SHIFT];
        end
      end else begin : with_add
        // in0 signed or has overlap
        if (IS_SUB == 1) begin : is_sub
          assign accum[BW_ADD-1:ABS_SHIFT] = in0_ext[BW_ADD-1:ABS_SHIFT] - in1_ext[BW_ADD-1:ABS_SHIFT];
        end else begin : is_add
          assign accum[BW_ADD-1:ABS_SHIFT] = in0_ext[BW_ADD-1:ABS_SHIFT] + in1_ext[BW_ADD-1:ABS_SHIFT];
        end
      end
    end else begin : shift_neg
      // lower |SHIFT1| bits
      if (IS_SUB == 0) begin : lower_add
        assign accum[ABS_SHIFT-1:0] = in1_ext[ABS_SHIFT-1:0];
      end else begin : lower_sub
        assign accum[ABS_SHIFT-1:0] = -in1_ext[ABS_SHIFT-1:0];
      end
      // upper bits
      if (ABS_SHIFT >= BW_INPUT1 && SIGNED1 == 0) begin : disjoint
        // in1 unsigned, disjoint
        if (IS_SUB == 0) begin : is_add
          assign accum[BW_ADD-1:ABS_SHIFT] = in0_ext[BW_ADD-1:ABS_SHIFT];
        end else begin : is_sub
          wire [BW_ADD-1-ABS_SHIFT:0] borrow = {{(BW_ADD-1-ABS_SHIFT){1'b0}}, |in1_ext[ABS_SHIFT-1:0]};
          assign accum[BW_ADD-1:ABS_SHIFT] = in0_ext[BW_ADD-1:ABS_SHIFT] - borrow;
        end
      end else begin : with_add
        // in1 signed or has overlap
        if (IS_SUB == 0) begin : is_add
          assign accum[BW_ADD-1:ABS_SHIFT] = in0_ext[BW_ADD-1:ABS_SHIFT] + in1_ext[BW_ADD-1:ABS_SHIFT];
        end else begin : is_sub
          wire [BW_ADD-1-ABS_SHIFT:0] borrow = {{(BW_ADD-1-ABS_SHIFT){1'b0}}, |in1_ext[ABS_SHIFT-1:0]};
          assign accum[BW_ADD-1:ABS_SHIFT] = in0_ext[BW_ADD-1:ABS_SHIFT] - in1_ext[BW_ADD-1:ABS_SHIFT] - borrow;
        end
      end
    end
  endgenerate
  assign out = accum[BW_OUT-1+DROP_LSBS:DROP_LSBS];

endmodule




module chipin_alk_ternary_adder #(
    parameter BW_INPUT0 = 32,
    parameter SIGNED0 = 0,
    parameter NEGATE0 = 0,
    parameter PAD0 = 0,
    parameter BW_INPUT1 = 32,
    parameter SIGNED1 = 0,
    parameter NEGATE1 = 0,
    parameter PAD1 = 0,
    parameter BW_INPUT2 = 32,
    parameter SIGNED2 = 0,
    parameter NEGATE2 = 0,
    parameter PAD2 = 0,
    parameter BW_OUT = 32,
    parameter DROP_LSBS = 0
) (
    input [BW_INPUT0-1:0] in0,
    input [BW_INPUT1-1:0] in1,
    input [BW_INPUT2-1:0] in2,
    output [BW_OUT-1:0] out
);

  function integer max2;
    input integer lhs;
    input integer rhs;
    begin
      max2 = (lhs > rhs) ? lhs : rhs;
    end
  endfunction

  function integer min2;
    input integer lhs;
    input integer rhs;
    begin
      min2 = (lhs < rhs) ? lhs : rhs;
    end
  endfunction

  function integer select3;
    input integer sel;
    input integer val0;
    input integer val1;
    input integer val2;
    begin
      select3 = (sel == 0) ? val0 : (sel == 1) ? val1 : val2;
    end
  endfunction

  localparam OUT_HIGH_ABS = DROP_LSBS + BW_OUT - 1;
  localparam MIN_PAD = min2(min2(PAD0, PAD1), PAD2);
  localparam LOW_COUNT = ((PAD0 == MIN_PAD) ? 1 : 0) + ((PAD1 == MIN_PAD) ? 1 : 0) + ((PAD2 == MIN_PAD) ? 1 : 0);
  localparam LOW_INPUT = (PAD0 == MIN_PAD) ? 0 : (PAD1 == MIN_PAD) ? 1 : 2;
  localparam LOW_NEGATE = select3(LOW_INPUT, NEGATE0, NEGATE1, NEGATE2);
  localparam NO_NEXT_PAD = OUT_HIGH_ABS + 2;
  localparam NEXT_PAD0 = (PAD0 > MIN_PAD) ? PAD0 : NO_NEXT_PAD;
  localparam NEXT_PAD1 = (PAD1 > MIN_PAD) ? PAD1 : NO_NEXT_PAD;
  localparam NEXT_PAD2 = (PAD2 > MIN_PAD) ? PAD2 : NO_NEXT_PAD;
  localparam UPPER_START = min2(min2(NEXT_PAD0, NEXT_PAD1), NEXT_PAD2);
  localparam LOW_COPY_ABS_LO = max2(DROP_LSBS, MIN_PAD);
  localparam LOW_COPY_ABS_HI = min2(OUT_HIGH_ABS, UPPER_START - 1);
  localparam LOWCOPY_ENABLE = (LOW_COUNT == 1) && (LOW_NEGATE == 0) && (UPPER_START != NO_NEXT_PAD) &&
                              (UPPER_START > DROP_LSBS) && (LOW_COPY_ABS_HI >= LOW_COPY_ABS_LO);

  localparam FULL_MAX_TERM_BW = max2(max2(BW_INPUT0 + PAD0, BW_INPUT1 + PAD1), BW_INPUT2 + PAD2);
  localparam FULL_BW_ADD = max2(FULL_MAX_TERM_BW + 4, BW_OUT + DROP_LSBS + 1);
  localparam FULL_LEFT_PAD0 = FULL_BW_ADD - BW_INPUT0 - PAD0;
  localparam FULL_LEFT_PAD1 = FULL_BW_ADD - BW_INPUT1 - PAD1;
  localparam FULL_LEFT_PAD2 = FULL_BW_ADD - BW_INPUT2 - PAD2;

  generate
    if (LOWCOPY_ENABLE) begin : lowcopy
      localparam LOW_PAD = select3(LOW_INPUT, PAD0, PAD1, PAD2);
      localparam LOW_OUT_LO = LOW_COPY_ABS_LO - DROP_LSBS;
      localparam LOW_OUT_HI = LOW_COPY_ABS_HI - DROP_LSBS;
      localparam ZERO_HI = min2(OUT_HIGH_ABS, LOW_PAD - 1) - DROP_LSBS;
      localparam SUFFIX_BW_RAW = OUT_HIGH_ABS - UPPER_START + 1;
      localparam SUFFIX_BW = (SUFFIX_BW_RAW > 0) ? SUFFIX_BW_RAW : 1;
      localparam SUFFIX_MAX_TERM_BW =
          max2(max2(max2(BW_INPUT0 + PAD0 - UPPER_START, 1), max2(BW_INPUT1 + PAD1 - UPPER_START, 1)),
               max2(BW_INPUT2 + PAD2 - UPPER_START, 1));
      localparam SUFFIX_BW_ADD = max2(SUFFIX_MAX_TERM_BW + 4, SUFFIX_BW + 1);
      localparam EXT_BW = max2(DROP_LSBS + BW_OUT, UPPER_START + SUFFIX_BW_ADD);
      localparam LEFT_PAD0 = EXT_BW - BW_INPUT0 - PAD0;
      localparam LEFT_PAD1 = EXT_BW - BW_INPUT1 - PAD1;
      localparam LEFT_PAD2 = EXT_BW - BW_INPUT2 - PAD2;

      // verilator lint_off UNUSEDSIGNAL
      wire [EXT_BW-1:0] in0_ext;
      wire [EXT_BW-1:0] in1_ext;
      wire [EXT_BW-1:0] in2_ext;

      if (SIGNED0 == 1) begin : in0_is_signed
        assign in0_ext = {{LEFT_PAD0{in0[BW_INPUT0-1]}}, in0, {PAD0{1'b0}}};
      end else begin : in0_is_unsigned
        assign in0_ext = {{LEFT_PAD0{1'b0}}, in0, {PAD0{1'b0}}};
      end

      if (SIGNED1 == 1) begin : in1_is_signed
        assign in1_ext = {{LEFT_PAD1{in1[BW_INPUT1-1]}}, in1, {PAD1{1'b0}}};
      end else begin : in1_is_unsigned
        assign in1_ext = {{LEFT_PAD1{1'b0}}, in1, {PAD1{1'b0}}};
      end

      if (SIGNED2 == 1) begin : in2_is_signed
        assign in2_ext = {{LEFT_PAD2{in2[BW_INPUT2-1]}}, in2, {PAD2{1'b0}}};
      end else begin : in2_is_unsigned
        assign in2_ext = {{LEFT_PAD2{1'b0}}, in2, {PAD2{1'b0}}};
      end

      wire signed [SUFFIX_BW_ADD-1:0] term0 =
          (NEGATE0 == 1) ? -$signed(in0_ext[UPPER_START+SUFFIX_BW_ADD-1:UPPER_START])
                         :  $signed(in0_ext[UPPER_START+SUFFIX_BW_ADD-1:UPPER_START]);
      wire signed [SUFFIX_BW_ADD-1:0] term1 =
          (NEGATE1 == 1) ? -$signed(in1_ext[UPPER_START+SUFFIX_BW_ADD-1:UPPER_START])
                         :  $signed(in1_ext[UPPER_START+SUFFIX_BW_ADD-1:UPPER_START]);
      wire signed [SUFFIX_BW_ADD-1:0] term2 =
          (NEGATE2 == 1) ? -$signed(in2_ext[UPPER_START+SUFFIX_BW_ADD-1:UPPER_START])
                         :  $signed(in2_ext[UPPER_START+SUFFIX_BW_ADD-1:UPPER_START]);
      wire signed [SUFFIX_BW_ADD-1:0] accum = term0 + term1 + term2;
      // verilator lint_on UNUSEDSIGNAL

      if (LOW_PAD > DROP_LSBS) begin : zero_low_bits
        assign out[ZERO_HI:0] = {(ZERO_HI + 1){1'b0}};
      end

      if (LOW_INPUT == 0) begin : low_from_in0
        assign out[LOW_OUT_HI:LOW_OUT_LO] = in0_ext[LOW_COPY_ABS_HI:LOW_COPY_ABS_LO];
      end else if (LOW_INPUT == 1) begin : low_from_in1
        assign out[LOW_OUT_HI:LOW_OUT_LO] = in1_ext[LOW_COPY_ABS_HI:LOW_COPY_ABS_LO];
      end else begin : low_from_in2
        assign out[LOW_OUT_HI:LOW_OUT_LO] = in2_ext[LOW_COPY_ABS_HI:LOW_COPY_ABS_LO];
      end

      if (UPPER_START <= OUT_HIGH_ABS) begin : add_upper_bits
        assign out[BW_OUT-1:UPPER_START-DROP_LSBS] = accum[SUFFIX_BW-1:0];
      end
    end else begin : full
      // verilator lint_off UNUSEDSIGNAL
      wire [FULL_BW_ADD-1:0] in0_ext;
      wire [FULL_BW_ADD-1:0] in1_ext;
      wire [FULL_BW_ADD-1:0] in2_ext;

      if (SIGNED0 == 1) begin : in0_is_signed
        assign in0_ext = {{FULL_LEFT_PAD0{in0[BW_INPUT0-1]}}, in0, {PAD0{1'b0}}};
      end else begin : in0_is_unsigned
        assign in0_ext = {{FULL_LEFT_PAD0{1'b0}}, in0, {PAD0{1'b0}}};
      end

      if (SIGNED1 == 1) begin : in1_is_signed
        assign in1_ext = {{FULL_LEFT_PAD1{in1[BW_INPUT1-1]}}, in1, {PAD1{1'b0}}};
      end else begin : in1_is_unsigned
        assign in1_ext = {{FULL_LEFT_PAD1{1'b0}}, in1, {PAD1{1'b0}}};
      end

      if (SIGNED2 == 1) begin : in2_is_signed
        assign in2_ext = {{FULL_LEFT_PAD2{in2[BW_INPUT2-1]}}, in2, {PAD2{1'b0}}};
      end else begin : in2_is_unsigned
        assign in2_ext = {{FULL_LEFT_PAD2{1'b0}}, in2, {PAD2{1'b0}}};
      end

      wire signed [FULL_BW_ADD-1:0] term0 = (NEGATE0 == 1) ? -$signed(in0_ext) : $signed(in0_ext);
      wire signed [FULL_BW_ADD-1:0] term1 = (NEGATE1 == 1) ? -$signed(in1_ext) : $signed(in1_ext);
      wire signed [FULL_BW_ADD-1:0] term2 = (NEGATE2 == 1) ? -$signed(in2_ext) : $signed(in2_ext);
      wire signed [FULL_BW_ADD-1:0] accum = term0 + term1 + term2;
      // verilator lint_on UNUSEDSIGNAL

      assign out = accum[BW_OUT-1+DROP_LSBS:DROP_LSBS];
    end
  endgenerate

endmodule

