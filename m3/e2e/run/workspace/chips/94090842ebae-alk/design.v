// optimizer: alkaid CSE for constant matvecs; the modules after `chip_94090842ebae` come from alkaid (LGPL-3.0)
// chipin.space chip lab: generated from chipir/1 design chip_94090842ebae. Do not edit; regenerate.
module chip_94090842ebae (
  input wire [39:0] x,
  output wire [0:0] y
);
  wire [3:0] i_x_0 = x[3:0];
  wire [3:0] i_x_1 = x[7:4];
  wire [3:0] i_x_2 = x[11:8];
  wire [3:0] i_x_3 = x[15:12];
  wire [3:0] i_x_4 = x[19:16];
  wire [3:0] i_x_5 = x[23:20];
  wire [3:0] i_x_6 = x[27:24];
  wire [3:0] i_x_7 = x[31:28];
  wire [3:0] i_x_8 = x[35:32];
  wire [3:0] i_x_9 = x[39:36];
  // matvec l0_mv: alkaid CSE shift-add network (16 of 16 rows)
  wire [39:0] mvi_l0_mv = {i_x_9, i_x_8, i_x_7, i_x_6, i_x_5, i_x_4, i_x_3, i_x_2, i_x_1, i_x_0};
  wire [120:0] mvo_l0_mv;
  chip_94090842ebae_mv_l0_mv u_chip_94090842ebae_mv_l0_mv (.model_inp(mvi_l0_mv), .model_out(mvo_l0_mv));
  wire [6:0] mvs_l0_mv_0 = mvo_l0_mv[6:0];
  wire [6:0] n_l0_mv_0 = mvs_l0_mv_0;
  wire [6:0] mvs_l0_mv_1 = mvo_l0_mv[13:7];
  wire [6:0] n_l0_mv_1 = mvs_l0_mv_1;
  wire [7:0] mvs_l0_mv_2 = mvo_l0_mv[21:14];
  wire [7:0] n_l0_mv_2 = mvs_l0_mv_2;
  wire [7:0] mvs_l0_mv_3 = mvo_l0_mv[29:22];
  wire [7:0] n_l0_mv_3 = mvs_l0_mv_3;
  wire [7:0] mvs_l0_mv_4 = mvo_l0_mv[37:30];
  wire [7:0] n_l0_mv_4 = mvs_l0_mv_4;
  wire [6:0] mvs_l0_mv_5 = mvo_l0_mv[44:38];
  wire [6:0] n_l0_mv_5 = mvs_l0_mv_5;
  wire [7:0] mvs_l0_mv_6 = mvo_l0_mv[52:45];
  wire [7:0] n_l0_mv_6 = mvs_l0_mv_6;
  wire [6:0] mvs_l0_mv_7 = mvo_l0_mv[59:53];
  wire [6:0] n_l0_mv_7 = mvs_l0_mv_7;
  wire [6:0] mvs_l0_mv_8 = mvo_l0_mv[66:60];
  wire [6:0] n_l0_mv_8 = mvs_l0_mv_8;
  wire [7:0] mvs_l0_mv_9 = mvo_l0_mv[74:67];
  wire [7:0] n_l0_mv_9 = mvs_l0_mv_9;
  wire [7:0] mvs_l0_mv_10 = mvo_l0_mv[82:75];
  wire [7:0] n_l0_mv_10 = mvs_l0_mv_10;
  wire [6:0] mvs_l0_mv_11 = mvo_l0_mv[89:83];
  wire [6:0] n_l0_mv_11 = mvs_l0_mv_11;
  wire [7:0] mvs_l0_mv_12 = mvo_l0_mv[97:90];
  wire [7:0] n_l0_mv_12 = mvs_l0_mv_12;
  wire [7:0] mvs_l0_mv_13 = mvo_l0_mv[105:98];
  wire [7:0] n_l0_mv_13 = mvs_l0_mv_13;
  wire [6:0] mvs_l0_mv_14 = mvo_l0_mv[112:106];
  wire [6:0] n_l0_mv_14 = mvs_l0_mv_14;
  wire [7:0] mvs_l0_mv_15 = mvo_l0_mv[120:113];
  wire [7:0] n_l0_mv_15 = mvs_l0_mv_15;
  wire [4:0] n_l0_sh_0 = n_l0_mv_0[6:2];
  wire [4:0] n_l0_sh_1 = n_l0_mv_1[6:2];
  wire [5:0] n_l0_sh_2 = n_l0_mv_2[7:2];
  wire [5:0] n_l0_sh_3 = n_l0_mv_3[7:2];
  wire [5:0] n_l0_sh_4 = n_l0_mv_4[7:2];
  wire [4:0] n_l0_sh_5 = n_l0_mv_5[6:2];
  wire [5:0] n_l0_sh_6 = n_l0_mv_6[7:2];
  wire [4:0] n_l0_sh_7 = n_l0_mv_7[6:2];
  wire [4:0] n_l0_sh_8 = n_l0_mv_8[6:2];
  wire [5:0] n_l0_sh_9 = n_l0_mv_9[7:2];
  wire [5:0] n_l0_sh_10 = n_l0_mv_10[7:2];
  wire [4:0] n_l0_sh_11 = n_l0_mv_11[6:2];
  wire [5:0] n_l0_sh_12 = n_l0_mv_12[7:2];
  wire [5:0] n_l0_sh_13 = n_l0_mv_13[7:2];
  wire [4:0] n_l0_sh_14 = n_l0_mv_14[6:2];
  wire [5:0] n_l0_sh_15 = n_l0_mv_15[7:2];
  wire [3:0] n_l0_0 = ($signed({{1{n_l0_sh_0[4]}}, n_l0_sh_0}) < $signed(6'd0)) ? 4'd0 : ($signed({{1{n_l0_sh_0[4]}}, n_l0_sh_0}) > $signed(6'd15)) ? 4'd15 : n_l0_sh_0[3:0];
  wire [3:0] n_l0_1 = ($signed({{1{n_l0_sh_1[4]}}, n_l0_sh_1}) < $signed(6'd0)) ? 4'd0 : ($signed({{1{n_l0_sh_1[4]}}, n_l0_sh_1}) > $signed(6'd15)) ? 4'd15 : n_l0_sh_1[3:0];
  wire [3:0] n_l0_2 = ($signed({{1{n_l0_sh_2[5]}}, n_l0_sh_2}) < $signed(7'd0)) ? 4'd0 : ($signed({{1{n_l0_sh_2[5]}}, n_l0_sh_2}) > $signed(7'd15)) ? 4'd15 : n_l0_sh_2[3:0];
  wire [3:0] n_l0_3 = ($signed({{1{n_l0_sh_3[5]}}, n_l0_sh_3}) < $signed(7'd0)) ? 4'd0 : ($signed({{1{n_l0_sh_3[5]}}, n_l0_sh_3}) > $signed(7'd15)) ? 4'd15 : n_l0_sh_3[3:0];
  wire [3:0] n_l0_4 = ($signed({{1{n_l0_sh_4[5]}}, n_l0_sh_4}) < $signed(7'd0)) ? 4'd0 : ($signed({{1{n_l0_sh_4[5]}}, n_l0_sh_4}) > $signed(7'd15)) ? 4'd15 : n_l0_sh_4[3:0];
  wire [2:0] n_l0_5 = ($signed({{1{n_l0_sh_5[4]}}, n_l0_sh_5}) < $signed(6'd0)) ? 3'd0 : ($signed({{1{n_l0_sh_5[4]}}, n_l0_sh_5}) > $signed(6'd15)) ? 3'd7 : n_l0_sh_5[2:0];
  wire [2:0] n_l0_6 = ($signed({{1{n_l0_sh_6[5]}}, n_l0_sh_6}) < $signed(7'd0)) ? 3'd0 : ($signed({{1{n_l0_sh_6[5]}}, n_l0_sh_6}) > $signed(7'd15)) ? 3'd7 : n_l0_sh_6[2:0];
  wire [3:0] n_l0_7 = ($signed({{1{n_l0_sh_7[4]}}, n_l0_sh_7}) < $signed(6'd0)) ? 4'd0 : ($signed({{1{n_l0_sh_7[4]}}, n_l0_sh_7}) > $signed(6'd15)) ? 4'd15 : n_l0_sh_7[3:0];
  wire [3:0] n_l0_8 = ($signed({{1{n_l0_sh_8[4]}}, n_l0_sh_8}) < $signed(6'd0)) ? 4'd0 : ($signed({{1{n_l0_sh_8[4]}}, n_l0_sh_8}) > $signed(6'd15)) ? 4'd15 : n_l0_sh_8[3:0];
  wire [3:0] n_l0_9 = ($signed({{1{n_l0_sh_9[5]}}, n_l0_sh_9}) < $signed(7'd0)) ? 4'd0 : ($signed({{1{n_l0_sh_9[5]}}, n_l0_sh_9}) > $signed(7'd15)) ? 4'd15 : n_l0_sh_9[3:0];
  wire [3:0] n_l0_10 = ($signed({{1{n_l0_sh_10[5]}}, n_l0_sh_10}) < $signed(7'd0)) ? 4'd0 : ($signed({{1{n_l0_sh_10[5]}}, n_l0_sh_10}) > $signed(7'd15)) ? 4'd15 : n_l0_sh_10[3:0];
  wire [2:0] n_l0_11 = ($signed({{1{n_l0_sh_11[4]}}, n_l0_sh_11}) < $signed(6'd0)) ? 3'd0 : ($signed({{1{n_l0_sh_11[4]}}, n_l0_sh_11}) > $signed(6'd15)) ? 3'd7 : n_l0_sh_11[2:0];
  wire [3:0] n_l0_12 = ($signed({{1{n_l0_sh_12[5]}}, n_l0_sh_12}) < $signed(7'd0)) ? 4'd0 : ($signed({{1{n_l0_sh_12[5]}}, n_l0_sh_12}) > $signed(7'd15)) ? 4'd15 : n_l0_sh_12[3:0];
  wire [3:0] n_l0_13 = ($signed({{1{n_l0_sh_13[5]}}, n_l0_sh_13}) < $signed(7'd0)) ? 4'd0 : ($signed({{1{n_l0_sh_13[5]}}, n_l0_sh_13}) > $signed(7'd15)) ? 4'd15 : n_l0_sh_13[3:0];
  wire [1:0] n_l0_14 = ($signed({{1{n_l0_sh_14[4]}}, n_l0_sh_14}) < $signed(6'd0)) ? 2'd0 : ($signed({{1{n_l0_sh_14[4]}}, n_l0_sh_14}) > $signed(6'd15)) ? 2'd3 : n_l0_sh_14[1:0];
  wire [0:0] n_l0_15 = ($signed({{1{n_l0_sh_15[5]}}, n_l0_sh_15}) < $signed(7'd0)) ? 1'd0 : ($signed({{1{n_l0_sh_15[5]}}, n_l0_sh_15}) > $signed(7'd15)) ? 1'd1 : n_l0_sh_15[0];
  // matvec score: alkaid CSE shift-add network (1 of 1 rows)
  wire [35:0] mvi_score = {n_l0_15, n_l0_14, n_l0_13, n_l0_12, n_l0_11, n_l0_10, n_l0_8, n_l0_7, n_l0_6, n_l0_5, n_l0_2};
  wire [7:0] mvo_score;
  chip_94090842ebae_mv_score u_chip_94090842ebae_mv_score (.model_inp(mvi_score), .model_out(mvo_score));
  wire [7:0] mvs_score_0 = mvo_score[7:0];
  wire [6:0] n_score_0 = mvs_score_0[6:0];
  wire [0:0] n_dec_0 = ($signed({{1{n_score_0[6]}}, n_score_0}) > $signed(8'd0)) ? 1'b1 : 1'b0;
  assign y = n_dec_0;
endmodule

module chip_94090842ebae_mv_l0_mv (
    input [39:0] model_inp,
    output [120:0] model_out
);

    // verilator lint_off UNUSEDSIGNAL
    // Explicit quantization operation will drop bits if exists

    wire [3:0] v0; assign v0[3:0] = model_inp[7:4];
    wire [3:0] v1; assign v1[3:0] = model_inp[35:32];
    wire [3:0] v2; assign v2[3:0] = model_inp[11:8];
    wire [4:0] v3; chipin_alk_shift_adder #(4,4,0,0,5,0,0,0) op_3 (v2[3:0],v1[3:0],v3[4:0]);
    wire [4:0] v4; chipin_alk_shift_adder #(4,4,0,0,5,0,0,1) op_4 (v2[3:0],v1[3:0],v4[4:0]);
    wire [3:0] v5; assign v5[3:0] = model_inp[27:24];
    wire [5:0] v6; chipin_alk_shift_adder #(5,4,0,0,6,0,0,1) op_6 (v3[4:0],v5[3:0],v6[5:0]);
    wire [3:0] v7; assign v7[3:0] = model_inp[31:28];
    wire [4:0] v8; chipin_alk_shift_adder #(4,4,0,0,5,0,0,0) op_8 (v5[3:0],v7[3:0],v8[4:0]);
    wire [4:0] v9; chipin_alk_shift_adder #(4,4,0,0,5,0,0,1) op_9 (v5[3:0],v7[3:0],v9[4:0]);
    wire [6:0] v10; chipin_alk_shift_adder #(5,5,1,0,7,0,0,0) op_10 (v9[4:0],v3[4:0],v10[6:0]);
    wire [3:0] v11; assign v11[3:0] = model_inp[3:0];
    wire [4:0] v12; chipin_alk_shift_adder #(4,4,0,0,5,0,0,1) op_12 (v11[3:0],v0[3:0],v12[4:0]);
    wire [5:0] v13; chipin_alk_shift_adder #(5,5,1,1,6,0,0,1) op_13 (v4[4:0],v12[4:0],v13[5:0]);
    wire [4:0] v14; chipin_alk_shift_adder #(4,4,0,0,5,0,0,0) op_14 (v11[3:0],v0[3:0],v14[4:0]);
    wire [3:0] v15; assign v15[3:0] = model_inp[23:20];
    wire [6:0] v16; chipin_alk_ternary_adder #(5,0,0,0,4,0,1,0,6,1,1,0,7,0) op_16 (v8[4:0],v15[3:0],v13[5:0],v16[6:0]);
    wire [7:0] v17; chipin_alk_shift_adder #(7,1,1,0,8,0,4,0) op_17 (v16[6:0],1'b1,v17[7:0]);
    wire [6:0] v18; chipin_alk_ternary_adder #(4,0,0,1,4,0,1,0,5,1,1,0,7,0) op_18 (v15[3:0],v2[3:0],v9[4:0],v18[6:0]);
    wire [3:0] v19; assign v19[3:0] = model_inp[39:36];
    wire [5:0] v20; chipin_alk_shift_adder #(4,5,0,1,6,0,0,1) op_20 (v19[3:0],v9[4:0],v20[5:0]);
    wire [7:0] v21; chipin_alk_ternary_adder #(5,0,0,0,4,0,0,0,6,1,0,0,8,0) op_21 (v3[4:0],v15[3:0],v20[5:0],v21[7:0]);
    wire [6:0] v22; chipin_alk_shift_adder #(8,5,1,0,7,0,0,0) op_22 (v21[7:0],5'b10001,v22[6:0]);
    wire [7:0] v23; chipin_alk_negative #(7, 8, 0) op_23 (v22, v23[7:0]);
    wire [6:0] v24; chipin_alk_shift_adder #(6,6,1,1,7,0,0,0) op_24 (v20[5:0],v13[5:0],v24[6:0]);
    wire [7:0] v25; chipin_alk_shift_adder #(7,4,1,0,8,0,0,0) op_25 (v24[6:0],4'b1011,v25[7:0]);
    wire [7:0] v26; chipin_alk_negative #(8, 8, 1) op_26 (v25, v26[7:0]);
    wire [6:0] v27; chipin_alk_shift_adder #(4,5,0,1,7,0,-1,1) op_27 (v19[3:0],v4[4:0],v27[6:0]);
    wire [3:0] v28; assign v28[3:0] = model_inp[19:16];
    wire [6:0] v29; chipin_alk_ternary_adder #(5,0,1,0,5,0,0,0,4,0,0,1,7,0) op_29 (v8[4:0],v3[4:0],v28[3:0],v29[6:0]);
    wire [5:0] v30; chipin_alk_shift_adder #(4,5,0,0,6,0,0,0) op_30 (v28[3:0],v8[4:0],v30[5:0]);
    wire [6:0] v31; chipin_alk_shift_adder #(6,4,0,0,7,0,0,1) op_31 (v30[5:0],v0[3:0],v31[6:0]);
    wire [6:0] v32; chipin_alk_ternary_adder #(4,0,0,0,4,0,0,0,6,0,1,0,7,0) op_32 (v11[3:0],v2[3:0],v30[5:0],v32[6:0]);
    wire [6:0] v33; chipin_alk_shift_adder #(7,1,1,0,7,0,1,1) op_33 (v32[6:0],1'b1,v33[6:0]);
    wire [6:0] v34; chipin_alk_ternary_adder #(4,0,0,0,4,0,1,1,5,0,1,0,7,0) op_34 (v19[3:0],v28[3:0],v14[4:0],v34[6:0]);
    wire [5:0] v35; chipin_alk_ternary_adder #(4,0,0,0,4,0,1,0,4,0,1,0,6,0) op_35 (v1[3:0],v28[3:0],v5[3:0],v35[5:0]);
    wire [4:0] v36; chipin_alk_shift_adder #(4,4,0,0,5,0,0,0) op_36 (v28[3:0],v11[3:0],v36[4:0]);
    wire [3:0] v37; assign v37[3:0] = model_inp[15:12];
    wire [5:0] v38; chipin_alk_ternary_adder #(4,0,0,0,4,0,1,0,4,0,1,0,6,0) op_38 (v7[3:0],v11[3:0],v37[3:0],v38[5:0]);
    wire [5:0] v39; chipin_alk_shift_adder #(4,5,0,1,6,0,0,0) op_39 (v37[3:0],v12[4:0],v39[5:0]);
    wire [5:0] v40; chipin_alk_shift_adder #(4,4,0,0,6,0,1,1) op_40 (v19[3:0],v37[3:0],v40[5:0]);
    wire [5:0] v41; chipin_alk_shift_adder #(4,4,0,0,6,0,-1,0) op_41 (v37[3:0],v7[3:0],v41[5:0]);
    wire [4:0] v42; chipin_alk_shift_adder #(4,4,0,0,5,0,0,1) op_42 (v37[3:0],v15[3:0],v42[4:0]);
    wire [6:0] v43; chipin_alk_ternary_adder #(5,0,0,0,5,1,0,0,5,0,1,0,7,0) op_43 (v14[4:0],v42[4:0],v8[4:0],v43[6:0]);
    wire [6:0] v44; chipin_alk_shift_adder #(7,2,1,0,7,0,0,1) op_44 (v43[6:0],2'b11,v44[6:0]);
    wire [4:0] v45; chipin_alk_shift_adder #(4,4,0,0,5,0,0,0) op_45 (v37[3:0],v15[3:0],v45[4:0]);
    wire [6:0] v46; chipin_alk_ternary_adder #(4,0,0,0,4,0,1,0,5,0,1,0,7,0) op_46 (v19[3:0],v28[3:0],v45[4:0],v46[6:0]);
    wire [7:0] v47; chipin_alk_ternary_adder #(6,1,0,0,7,1,0,0,7,1,0,0,8,0) op_47 (v39[5:0],v29[6:0],v46[6:0],v47[7:0]);
    wire [7:0] v48; chipin_alk_shift_adder #(8,2,1,0,8,0,2,1) op_48 (v47[7:0],2'b11,v48[7:0]);
    wire [7:0] v49; chipin_alk_ternary_adder #(7,1,0,0,7,1,1,0,7,1,0,0,8,0) op_49 (v31[6:0],v27[6:0],v46[6:0],v49[7:0]);
    wire [7:0] v50; chipin_alk_shift_adder #(8,1,1,0,8,0,4,1) op_50 (v49[7:0],1'b1,v50[7:0]);
    wire [7:0] v51; chipin_alk_ternary_adder #(4,0,0,1,7,1,0,0,7,1,0,0,8,0) op_51 (v37[3:0],v29[6:0],v46[6:0],v51[7:0]);
    wire [7:0] v52; chipin_alk_shift_adder #(8,3,1,0,8,0,0,0) op_52 (v51[7:0],3'b101,v52[7:0]);
    wire [7:0] v53; chipin_alk_ternary_adder #(7,1,0,0,7,1,0,0,7,1,1,0,8,0) op_53 (v10[6:0],v34[6:0],v46[6:0],v53[7:0]);
    wire [7:0] v54; chipin_alk_shift_adder #(8,4,1,0,8,0,1,0) op_54 (v53[7:0],4'b1001,v54[7:0]);
    wire [7:0] v55; chipin_alk_ternary_adder #(7,1,0,0,5,0,1,0,7,1,0,0,8,0) op_55 (v18[6:0],v14[4:0],v46[6:0],v55[7:0]);
    wire [7:0] v56; chipin_alk_shift_adder #(8,4,1,0,8,0,1,0) op_56 (v55[7:0],4'b1001,v56[7:0]);
    wire [7:0] v57; chipin_alk_ternary_adder #(6,1,0,0,7,1,0,0,7,1,1,0,8,0) op_57 (v38[5:0],v27[6:0],v46[6:0],v57[7:0]);
    wire [7:0] v58; chipin_alk_shift_adder #(8,3,1,0,8,0,1,0) op_58 (v57[7:0],3'b111,v58[7:0]);
    wire [7:0] v59; chipin_alk_ternary_adder #(5,0,0,1,6,1,0,0,7,1,0,0,8,0) op_59 (v45[4:0],v6[5:0],v46[6:0],v59[7:0]);
    wire [6:0] v60; chipin_alk_shift_adder #(8,1,1,0,7,0,4,1) op_60 (v59[7:0],1'b1,v60[6:0]);
    wire [6:0] v61; chipin_alk_ternary_adder #(6,1,0,0,5,0,1,0,7,1,1,0,7,0) op_61 (v35[5:0],v14[4:0],v46[6:0],v61[6:0]);
    wire [6:0] v62; chipin_alk_shift_adder #(7,4,1,0,7,0,0,0) op_62 (v61[6:0],4'b1001,v62[6:0]);
    wire [6:0] v63; chipin_alk_ternary_adder #(5,0,0,0,6,1,0,0,7,1,1,0,7,0) op_63 (v8[4:0],v40[5:0],v46[6:0],v63[6:0]);
    wire [6:0] v64; chipin_alk_shift_adder #(7,1,1,0,7,0,1,1) op_64 (v63[6:0],1'b1,v64[6:0]);
    wire [6:0] v65; chipin_alk_ternary_adder #(6,0,0,0,5,0,0,0,7,1,0,0,7,0) op_65 (v41[5:0],v36[4:0],v46[6:0],v65[6:0]);
    wire [6:0] v66; chipin_alk_shift_adder #(7,4,1,0,7,0,0,1) op_66 (v65[6:0],4'b1111,v66[6:0]);
    wire [6:0] v67; chipin_alk_negative #(7, 7, 1) op_67 (v66, v67[6:0]);
    wire [6:0] v68; chipin_alk_shift_adder #(7,1,1,0,7,0,2,1) op_68 (v46[6:0],1'b1,v68[6:0]);

    // verilator lint_on UNUSEDSIGNAL

    assign model_out[6:0] = v44[6:0];
    assign model_out[13:7] = v62[6:0];
    assign model_out[21:14] = v48[7:0];
    assign model_out[29:22] = v58[7:0];
    assign model_out[37:30] = v56[7:0];
    assign model_out[44:38] = v67[6:0];
    assign model_out[52:45] = v50[7:0];
    assign model_out[59:53] = v60[6:0];
    assign model_out[66:60] = v64[6:0];
    assign model_out[74:67] = v17[7:0];
    assign model_out[82:75] = v52[7:0];
    assign model_out[89:83] = v33[6:0];
    assign model_out[97:90] = v54[7:0];
    assign model_out[105:98] = v26[7:0];
    assign model_out[112:106] = v68[6:0];
    assign model_out[120:113] = v23[7:0];

endmodule

module chip_94090842ebae_mv_score (
    input [35:0] model_inp,
    output [7:0] model_out
);

    // verilator lint_off UNUSEDSIGNAL
    // Explicit quantization operation will drop bits if exists

    wire [0:0] v0; assign v0[0:0] = model_inp[35:35];
    wire [1:0] v1; assign v1[1:0] = model_inp[34:33];
    wire [2:0] v2; assign v2[2:0] = model_inp[6:4];
    wire [2:0] v3; assign v3[2:0] = model_inp[9:7];
    wire [2:0] v4; assign v4[2:0] = model_inp[24:22];
    wire [3:0] v5; chipin_alk_shift_adder #(3,3,0,0,4,0,0,0) op_5 (v2[2:0],v4[2:0],v5[3:0]);
    wire [3:0] v6; assign v6[3:0] = model_inp[3:0];
    wire [3:0] v7; assign v7[3:0] = model_inp[13:10];
    wire [5:0] v8; chipin_alk_ternary_adder #(4,0,0,0,4,0,0,0,4,0,0,0,6,0) op_8 (v6[3:0],v7[3:0],v5[3:0],v8[5:0]);
    wire [3:0] v9; assign v9[3:0] = model_inp[17:14];
    wire [4:0] v10; chipin_alk_shift_adder #(4,3,0,0,5,0,0,0) op_10 (v9[3:0],v3[2:0],v10[4:0]);
    wire [3:0] v11; assign v11[3:0] = model_inp[21:18];
    wire [4:0] v12; chipin_alk_ternary_adder #(1,0,0,0,2,0,0,0,4,0,1,0,5,0) op_12 (v0[0:0],v1[1:0],v11[3:0],v12[4:0]);
    wire [3:0] v13; assign v13[3:0] = model_inp[28:25];
    wire [3:0] v14; assign v14[3:0] = model_inp[32:29];
    wire [5:0] v15; chipin_alk_ternary_adder #(4,0,0,0,4,0,0,0,5,0,1,0,6,0) op_15 (v13[3:0],v14[3:0],v10[4:0],v15[5:0]);
    wire [7:0] v16; chipin_alk_ternary_adder #(5,1,0,0,6,1,0,0,6,0,0,0,8,0) op_16 (v12[4:0],v15[5:0],v8[5:0],v16[7:0]);
    wire [7:0] v17; chipin_alk_shift_adder #(8,3,1,0,8,0,0,1) op_17 (v16[7:0],3'b101,v17[7:0]);

    // verilator lint_on UNUSEDSIGNAL

    assign model_out[7:0] = v17[7:0];

endmodule




module chipin_alk_negative #(
    parameter BW_IN = 32,
    parameter BW_OUT = 32,
    parameter IN_SIGNED = 0
) (
    // verilator lint_off UNUSEDSIGNAL
    input  [ BW_IN-1:0] in,
    // verilator lint_off UNUSEDSIGNAL
    output [BW_OUT-1:0] out
);
  /* verilator lint_off WIDTHTRUNC */
  generate
    if (BW_IN < BW_OUT) begin : in_is_smaller
      wire [BW_OUT-1:0] in_ext;
      if (IN_SIGNED == 1) begin : is_signed
        assign in_ext = {{BW_OUT - BW_IN{in[BW_IN-1]}}, in};
      end else begin : is_unsigned
        assign in_ext = {{BW_OUT - BW_IN{1'b0}}, in};
      end
      assign out = -in_ext;
    end else begin : in_is_bigger
      wire [BW_IN-1:0] out_ext;
      assign out_ext = -in;
      assign out = out_ext[BW_OUT-1:0];
    end
  endgenerate
  /* verilator lint_on WIDTHTRUNC */
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

