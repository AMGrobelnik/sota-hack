// optimizer: alkaid CSE for constant matvecs; the modules after `chip_67301286c5e3` come from alkaid (LGPL-3.0)
// chipin.space chip lab: generated from chipir/1 design chip_67301286c5e3. Do not edit; regenerate.
module chip_67301286c5e3 (
  input wire [47:0] x,
  output wire [0:0] y
);
  wire [5:0] i_x_0 = x[5:0];
  wire [5:0] i_x_1 = x[11:6];
  wire [5:0] i_x_2 = x[17:12];
  wire [5:0] i_x_3 = x[23:18];
  wire [5:0] i_x_4 = x[29:24];
  wire [5:0] i_x_5 = x[35:30];
  wire [5:0] i_x_6 = x[41:36];
  wire [5:0] i_x_7 = x[47:42];
  // matvec l0_mv: alkaid CSE shift-add network (8 of 8 rows)
  wire [47:0] mvi_l0_mv = {i_x_7, i_x_6, i_x_5, i_x_4, i_x_3, i_x_2, i_x_1, i_x_0};
  wire [93:0] mvo_l0_mv;
  chip_67301286c5e3_mv_l0_mv u_chip_67301286c5e3_mv_l0_mv (.model_inp(mvi_l0_mv), .model_out(mvo_l0_mv));
  wire [10:0] mvs_l0_mv_0 = mvo_l0_mv[10:0];
  wire [10:0] n_l0_mv_0 = mvs_l0_mv_0;
  wire [11:0] mvs_l0_mv_1 = mvo_l0_mv[22:11];
  wire [11:0] n_l0_mv_1 = mvs_l0_mv_1;
  wire [10:0] mvs_l0_mv_2 = mvo_l0_mv[33:23];
  wire [10:0] n_l0_mv_2 = mvs_l0_mv_2;
  wire [11:0] mvs_l0_mv_3 = mvo_l0_mv[45:34];
  wire [11:0] n_l0_mv_3 = mvs_l0_mv_3;
  wire [11:0] mvs_l0_mv_4 = mvo_l0_mv[57:46];
  wire [11:0] n_l0_mv_4 = mvs_l0_mv_4;
  wire [11:0] mvs_l0_mv_5 = mvo_l0_mv[69:58];
  wire [11:0] n_l0_mv_5 = mvs_l0_mv_5;
  wire [11:0] mvs_l0_mv_6 = mvo_l0_mv[81:70];
  wire [11:0] n_l0_mv_6 = mvs_l0_mv_6;
  wire [11:0] mvs_l0_mv_7 = mvo_l0_mv[93:82];
  wire [11:0] n_l0_mv_7 = mvs_l0_mv_7;
  wire [4:0] n_l0_sh_0 = n_l0_mv_0[10:6];
  wire [5:0] n_l0_sh_1 = n_l0_mv_1[11:6];
  wire [4:0] n_l0_sh_2 = n_l0_mv_2[10:6];
  wire [5:0] n_l0_sh_3 = n_l0_mv_3[11:6];
  wire [5:0] n_l0_sh_4 = n_l0_mv_4[11:6];
  wire [5:0] n_l0_sh_5 = n_l0_mv_5[11:6];
  wire [5:0] n_l0_sh_6 = n_l0_mv_6[11:6];
  wire [5:0] n_l0_sh_7 = n_l0_mv_7[11:6];
  wire [3:0] n_l0_0 = ($signed({{1{n_l0_sh_0[4]}}, n_l0_sh_0}) < $signed(6'd0)) ? 4'd0 : ($signed({{1{n_l0_sh_0[4]}}, n_l0_sh_0}) > $signed(6'd15)) ? 4'd15 : n_l0_sh_0[3:0];
  wire [2:0] n_l0_1 = ($signed({{1{n_l0_sh_1[5]}}, n_l0_sh_1}) < $signed(7'd0)) ? 3'd0 : ($signed({{1{n_l0_sh_1[5]}}, n_l0_sh_1}) > $signed(7'd15)) ? 3'd7 : n_l0_sh_1[2:0];
  wire [2:0] n_l0_2 = ($signed({{1{n_l0_sh_2[4]}}, n_l0_sh_2}) < $signed(6'd0)) ? 3'd0 : ($signed({{1{n_l0_sh_2[4]}}, n_l0_sh_2}) > $signed(6'd15)) ? 3'd7 : n_l0_sh_2[2:0];
  wire [3:0] n_l0_3 = ($signed({{1{n_l0_sh_3[5]}}, n_l0_sh_3}) < $signed(7'd0)) ? 4'd0 : ($signed({{1{n_l0_sh_3[5]}}, n_l0_sh_3}) > $signed(7'd15)) ? 4'd15 : n_l0_sh_3[3:0];
  wire [3:0] n_l0_4 = ($signed({{1{n_l0_sh_4[5]}}, n_l0_sh_4}) < $signed(7'd0)) ? 4'd0 : ($signed({{1{n_l0_sh_4[5]}}, n_l0_sh_4}) > $signed(7'd15)) ? 4'd15 : n_l0_sh_4[3:0];
  wire [3:0] n_l0_5 = ($signed({{1{n_l0_sh_5[5]}}, n_l0_sh_5}) < $signed(7'd0)) ? 4'd0 : ($signed({{1{n_l0_sh_5[5]}}, n_l0_sh_5}) > $signed(7'd15)) ? 4'd15 : n_l0_sh_5[3:0];
  wire [3:0] n_l0_6 = ($signed({{1{n_l0_sh_6[5]}}, n_l0_sh_6}) < $signed(7'd0)) ? 4'd0 : ($signed({{1{n_l0_sh_6[5]}}, n_l0_sh_6}) > $signed(7'd15)) ? 4'd15 : n_l0_sh_6[3:0];
  wire [2:0] n_l0_7 = ($signed({{1{n_l0_sh_7[5]}}, n_l0_sh_7}) < $signed(7'd0)) ? 3'd0 : ($signed({{1{n_l0_sh_7[5]}}, n_l0_sh_7}) > $signed(7'd15)) ? 3'd7 : n_l0_sh_7[2:0];
  // matvec score: alkaid CSE shift-add network (1 of 1 rows)
  wire [28:0] mvi_score = {n_l0_7, n_l0_6, n_l0_5, n_l0_4, n_l0_3, n_l0_2, n_l0_1, n_l0_0};
  wire [8:0] mvo_score;
  chip_67301286c5e3_mv_score u_chip_67301286c5e3_mv_score (.model_inp(mvi_score), .model_out(mvo_score));
  wire [8:0] mvs_score_0 = mvo_score[8:0];
  wire [8:0] n_score_0 = mvs_score_0;
  wire [0:0] n_dec_0 = ($signed({{1{n_score_0[8]}}, n_score_0}) > $signed(10'd0)) ? 1'b1 : 1'b0;
  assign y = n_dec_0;
endmodule

module chip_67301286c5e3_mv_l0_mv (
    input [47:0] model_inp,
    output [93:0] model_out
);

    // verilator lint_off UNUSEDSIGNAL
    // Explicit quantization operation will drop bits if exists

    wire [5:0] v0; assign v0[5:0] = model_inp[11:6];
    wire [5:0] v1; assign v1[5:0] = model_inp[29:24];
    wire [5:0] v2; assign v2[5:0] = model_inp[35:30];
    wire [5:0] v3; assign v3[5:0] = model_inp[47:42];
    wire [7:0] v4; chipin_alk_shift_adder #(6,6,0,0,8,0,-1,1) op_4 (v2[5:0],v3[5:0],v4[7:0]);
    wire [5:0] v5; assign v5[5:0] = model_inp[5:0];
    wire [7:0] v6; chipin_alk_shift_adder #(6,6,0,0,8,0,1,0) op_6 (v5[5:0],v2[5:0],v6[7:0]);
    wire [6:0] v7; chipin_alk_shift_adder #(6,6,0,0,7,0,0,0) op_7 (v5[5:0],v1[5:0],v7[6:0]);
    wire [5:0] v8; assign v8[5:0] = model_inp[17:12];
    wire [6:0] v9; chipin_alk_shift_adder #(6,6,0,0,7,0,0,1) op_9 (v8[5:0],v3[5:0],v9[6:0]);
    wire [7:0] v10; chipin_alk_shift_adder #(7,6,1,0,8,0,0,1) op_10 (v9[6:0],v5[5:0],v10[7:0]);
    wire [7:0] v11; chipin_alk_shift_adder #(6,6,0,0,8,0,-1,0) op_11 (v8[5:0],v1[5:0],v11[7:0]);
    wire [9:0] v12; chipin_alk_ternary_adder #(6,0,0,3,8,0,1,1,6,0,0,0,10,0) op_12 (v1[5:0],v11[7:0],v5[5:0],v12[9:0]);
    wire [10:0] v13; chipin_alk_ternary_adder #(6,0,0,0,6,0,0,0,7,0,0,3,11,0) op_13 (v8[5:0],v0[5:0],v7[6:0],v13[10:0]);
    wire [5:0] v14; assign v14[5:0] = model_inp[41:36];
    wire [8:0] v15; chipin_alk_shift_adder #(6,6,0,0,9,0,-2,1) op_15 (v0[5:0],v14[5:0],v15[8:0]);
    wire [9:0] v16; chipin_alk_shift_adder #(9,7,1,0,10,0,0,0) op_16 (v15[8:0],v7[6:0],v16[9:0]);
    wire [9:0] v17; chipin_alk_ternary_adder #(6,0,0,1,6,0,1,1,8,0,0,0,10,0) op_17 (v14[5:0],v1[5:0],v6[7:0],v17[9:0]);
    wire [7:0] v18; chipin_alk_shift_adder #(6,6,0,0,8,0,1,0) op_18 (v0[5:0],v14[5:0],v18[7:0]);
    wire [9:0] v19; chipin_alk_shift_adder #(8,6,0,0,10,0,3,1) op_19 (v18[7:0],v3[5:0],v19[9:0]);
    wire [8:0] v20; chipin_alk_shift_adder #(8,8,0,1,9,0,0,1) op_20 (v18[7:0],v4[7:0],v20[8:0]);
    wire [8:0] v21; chipin_alk_shift_adder #(6,6,0,0,9,0,-2,1) op_21 (v5[5:0],v14[5:0],v21[8:0]);
    wire [10:0] v22; chipin_alk_ternary_adder #(9,1,0,1,9,1,1,0,10,1,0,0,11,0) op_22 (v20[8:0],v21[8:0],v12[9:0],v22[10:0]);
    wire [11:0] v23; chipin_alk_shift_adder #(11,4,1,0,12,0,4,0) op_23 (v22[10:0],4'b1001,v23[11:0]);
    wire [5:0] v24; assign v24[5:0] = model_inp[23:18];
    wire [9:0] v25; chipin_alk_ternary_adder #(6,0,0,0,6,0,0,1,9,1,0,0,10,0) op_25 (v2[5:0],v24[5:0],v15[8:0],v25[9:0]);
    wire [11:0] v26; chipin_alk_ternary_adder #(10,1,0,0,7,1,1,0,10,1,0,1,12,0) op_26 (v25[9:0],v9[6:0],v17[9:0],v26[11:0]);
    wire [11:0] v27; chipin_alk_shift_adder #(12,8,1,0,12,0,0,0) op_27 (v26[11:0],8'b10111101,v27[11:0]);
    wire [8:0] v28; chipin_alk_shift_adder #(6,6,0,0,9,0,-2,0) op_28 (v24[5:0],v3[5:0],v28[8:0]);
    wire [9:0] v29; chipin_alk_ternary_adder #(6,0,0,0,6,0,0,3,9,0,0,0,10,0) op_29 (v24[5:0],v14[5:0],v28[8:0],v29[9:0]);
    wire [11:0] v30; chipin_alk_ternary_adder #(8,1,0,2,10,0,0,0,10,1,0,0,12,0) op_30 (v10[7:0],v29[9:0],v16[9:0],v30[11:0]);
    wire [11:0] v31; chipin_alk_shift_adder #(12,7,1,0,12,0,0,0) op_31 (v30[11:0],7'b1010011,v31[11:0]);
    wire [9:0] v32; chipin_alk_shift_adder #(9,8,0,0,10,0,1,0) op_32 (v28[8:0],v6[7:0],v32[9:0]);
    wire [10:0] v33; chipin_alk_shift_adder #(9,9,0,1,11,0,-1,0) op_33 (v28[8:0],v15[8:0],v33[10:0]);
    wire [6:0] v34; chipin_alk_shift_adder #(6,6,0,0,7,0,0,1) op_34 (v24[5:0],v2[5:0],v34[6:0]);
    wire [8:0] v35; chipin_alk_ternary_adder #(6,0,0,1,6,0,0,0,7,1,0,0,9,0) op_35 (v5[5:0],v0[5:0],v34[6:0],v35[8:0]);
    wire [9:0] v36; chipin_alk_shift_adder #(7,7,1,1,10,0,2,0) op_36 (v34[6:0],v34[6:0],v36[9:0]);
    wire [11:0] v37; chipin_alk_ternary_adder #(10,1,0,0,11,0,1,0,10,1,0,0,12,0) op_37 (v36[9:0],v13[10:0],v16[9:0],v37[11:0]);
    wire [11:0] v38; chipin_alk_shift_adder #(12,7,1,0,12,0,0,1) op_38 (v37[11:0],7'b1101001,v38[11:0]);
    wire [10:0] v39; chipin_alk_ternary_adder #(7,1,0,2,7,1,1,0,8,0,1,1,11,0) op_39 (v34[6:0],v34[6:0],v11[7:0],v39[10:0]);
    wire [10:0] v40; chipin_alk_ternary_adder #(6,0,0,0,9,1,0,0,11,1,0,0,11,0) op_40 (v3[5:0],v21[8:0],v39[10:0],v40[10:0]);
    wire [10:0] v41; chipin_alk_shift_adder #(11,7,1,0,11,0,0,1) op_41 (v40[10:0],7'b1101011,v41[10:0]);
    wire [6:0] v42; chipin_alk_shift_adder #(6,6,0,0,7,0,0,0) op_42 (v1[5:0],v24[5:0],v42[6:0]);
    wire [8:0] v43; chipin_alk_ternary_adder #(6,0,0,2,6,0,0,0,7,0,0,0,9,0) op_43 (v8[5:0],v2[5:0],v42[6:0],v43[8:0]);
    wire [10:0] v44; chipin_alk_ternary_adder #(10,1,0,0,10,0,0,0,9,0,1,0,11,0) op_44 (v19[9:0],v32[9:0],v43[8:0],v44[10:0]);
    wire [10:0] v45; chipin_alk_shift_adder #(11,5,1,0,11,0,1,0) op_45 (v44[10:0],5'b10001,v45[10:0]);
    wire [6:0] v46; chipin_alk_shift_adder #(6,6,0,0,7,0,0,0) op_46 (v8[5:0],v24[5:0],v46[6:0]);
    wire [11:0] v47; chipin_alk_ternary_adder #(8,1,0,1,7,0,0,3,9,1,1,0,12,0) op_47 (v4[7:0],v46[6:0],v35[8:0],v47[11:0]);
    wire [11:0] v48; chipin_alk_ternary_adder #(8,0,1,0,9,1,1,0,12,1,0,0,12,0) op_48 (v11[7:0],v15[8:0],v47[11:0],v48[11:0]);
    wire [11:0] v49; chipin_alk_shift_adder #(12,2,1,0,12,0,4,1) op_49 (v48[11:0],2'b11,v49[11:0]);
    wire [6:0] v50; chipin_alk_shift_adder #(6,6,0,0,7,0,0,0) op_50 (v0[5:0],v24[5:0],v50[6:0]);
    wire [9:0] v51; chipin_alk_ternary_adder #(6,0,0,2,6,0,1,0,7,0,0,0,10,0) op_51 (v14[5:0],v8[5:0],v50[6:0],v51[9:0]);
    wire [11:0] v52; chipin_alk_ternary_adder #(10,1,0,0,11,1,1,0,10,1,1,0,12,0) op_52 (v51[9:0],v33[10:0],v12[9:0],v52[11:0]);
    wire [11:0] v53; chipin_alk_shift_adder #(12,1,1,0,12,0,0,0) op_53 (v52[11:0],1'b1,v53[11:0]);

    // verilator lint_on UNUSEDSIGNAL

    assign model_out[10:0] = v45[10:0];
    assign model_out[22:11] = v38[11:0];
    assign model_out[33:23] = v41[10:0];
    assign model_out[45:34] = v31[11:0];
    assign model_out[57:46] = v49[11:0];
    assign model_out[69:58] = v27[11:0];
    assign model_out[81:70] = v23[11:0];
    assign model_out[93:82] = v53[11:0];

endmodule

module chip_67301286c5e3_mv_score (
    input [28:0] model_inp,
    output [8:0] model_out
);

    // verilator lint_off UNUSEDSIGNAL
    // Explicit quantization operation will drop bits if exists

    wire [2:0] v0; assign v0[2:0] = model_inp[6:4];
    wire [2:0] v1; assign v1[2:0] = model_inp[9:7];
    wire [2:0] v2; assign v2[2:0] = model_inp[28:26];
    wire [4:0] v3; chipin_alk_shift_adder #(3,3,0,0,5,0,1,0) op_3 (v1[2:0],v2[2:0],v3[4:0]);
    wire [3:0] v4; assign v4[3:0] = model_inp[13:10];
    wire [3:0] v5; assign v5[3:0] = model_inp[17:14];
    wire [4:0] v6; chipin_alk_shift_adder #(3,4,0,0,5,0,0,0) op_6 (v0[2:0],v5[3:0],v6[4:0]);
    wire [3:0] v7; assign v7[3:0] = model_inp[21:18];
    wire [3:0] v8; assign v8[3:0] = model_inp[25:22];
    wire [3:0] v9; assign v9[3:0] = model_inp[3:0];
    wire [5:0] v10; chipin_alk_shift_adder #(4,4,0,0,6,0,1,0) op_10 (v9[3:0],v4[3:0],v10[5:0]);
    wire [7:0] v11; chipin_alk_ternary_adder #(4,0,0,2,4,0,1,0,6,0,0,0,8,0) op_11 (v7[3:0],v8[3:0],v10[5:0],v11[7:0]);
    wire [7:0] v12; chipin_alk_ternary_adder #(5,0,0,0,4,0,1,2,8,1,0,0,8,0) op_12 (v3[4:0],v9[3:0],v11[7:0],v12[7:0]);
    wire [8:0] v13; chipin_alk_ternary_adder #(5,0,1,2,5,0,1,0,8,1,0,0,9,0) op_13 (v6[4:0],v6[4:0],v12[7:0],v13[8:0]);
    wire [8:0] v14; chipin_alk_shift_adder #(9,1,1,0,9,0,1,1) op_14 (v13[8:0],1'b1,v14[8:0]);

    // verilator lint_on UNUSEDSIGNAL

    assign model_out[8:0] = v14[8:0];

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

