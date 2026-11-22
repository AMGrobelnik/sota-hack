// chipin.space chip lab: generated from chipir/1 design chip_e05449cf23de. Do not edit; regenerate.
module chip_e05449cf23de (
  input wire [23:0] x,
  input wire [23:0] xp,
  input wire [41:0] acc,
  output wire [41:0] y
);
  wire [11:0] i_x_0 = x[11:0];
  wire [11:0] i_x_1 = x[23:12];
  wire [11:0] i_xp_0 = xp[11:0];
  wire [11:0] i_xp_1 = xp[23:12];
  wire [20:0] i_acc_0 = acc[20:0];
  wire [20:0] i_acc_1 = acc[41:21];
  wire [12:0] n_d_0 = {{1{i_x_0[11]}}, i_x_0} - {{1{i_xp_0[11]}}, i_xp_0};
  wire [12:0] n_d_1 = {{1{i_x_1[11]}}, i_x_1} - {{1{i_xp_1[11]}}, i_xp_1};
  wire [13:0] n_ad_0_t1 = n_d_0[12] ? (14'd0 - {{1{n_d_0[12]}}, n_d_0}) : {{1{n_d_0[12]}}, n_d_0};
  wire [11:0] n_ad_0 = n_ad_0_t1[11:0];
  wire [13:0] n_ad_1_t2 = n_d_1[12] ? (14'd0 - {{1{n_d_1[12]}}, n_d_1}) : {{1{n_d_1[12]}}, n_d_1};
  wire [11:0] n_ad_1 = n_ad_1_t2[11:0];
  wire [21:0] n_s_0 = {{1{1'b0}}, i_acc_0} + {{10{1'b0}}, n_ad_0};
  wire [21:0] n_s_1 = {{1{1'b0}}, i_acc_1} + {{10{1'b0}}, n_ad_1};
  wire [20:0] n_y_0 = ($signed({{2{1'b0}}, n_s_0}) < $signed(24'd0)) ? 21'd0 : ($signed({{2{1'b0}}, n_s_0}) > $signed(24'd2097151)) ? 21'd2097151 : n_s_0[20:0];
  wire [20:0] n_y_1 = ($signed({{2{1'b0}}, n_s_1}) < $signed(24'd0)) ? 21'd0 : ($signed({{2{1'b0}}, n_s_1}) > $signed(24'd2097151)) ? 21'd2097151 : n_s_1[20:0];
  assign y = {n_y_1, n_y_0};
endmodule
