// chipin.space chip lab: generated from chipir/1 design chip_1e554783d832. Do not edit; regenerate.
module chip_1e554783d832 (
  input wire [7:0] x,
  input wire [31:0] h,
  input wire [13:0] c,
  input wire [6:0] p,
  output wire [0:0] af,
  output wire [0:0] done,
  output wire [31:0] h_next,
  output wire [13:0] c_next,
  output wire [6:0] p_next
);
  wire [7:0] i_x_0 = x[7:0];
  wire [7:0] i_h_0 = h[7:0];
  wire [7:0] i_h_1 = h[15:8];
  wire [7:0] i_h_2 = h[23:16];
  wire [7:0] i_h_3 = h[31:24];
  wire [6:0] i_c_0 = c[6:0];
  wire [6:0] i_c_1 = c[13:7];
  wire [6:0] i_p_0 = p[6:0];
  wire [7:0] n_h3_0 = i_h_2;
  wire [3:0] n_s3_4_0 = n_h3_0[7:4];
  wire [8:0] n_e3_0 = {{1{1'b0}}, i_x_0} - {{1{1'b0}}, n_h3_0};
  wire [9:0] n_ae3_0_t1 = n_e3_0[8] ? (10'd0 - {{1{n_e3_0[8]}}, n_e3_0}) : {{1{n_e3_0[8]}}, n_e3_0};
  wire [7:0] n_ae3_0 = n_ae3_0_t1[7:0];
  wire [0:0] n_b_rel3_4_0 = ($signed({{2{1'b0}}, n_ae3_0}) > $signed({{6{1'b0}}, n_s3_4_0})) ? 1'b1 : 1'b0;
  wire [7:0] n_h4_0 = i_h_3;
  wire [2:0] n_s4_5_0 = n_h4_0[7:5];
  wire [8:0] n_e4_0 = {{1{1'b0}}, i_x_0} - {{1{1'b0}}, n_h4_0};
  wire [9:0] n_ae4_0_t2 = n_e4_0[8] ? (10'd0 - {{1{n_e4_0[8]}}, n_e4_0}) : {{1{n_e4_0[8]}}, n_e4_0};
  wire [7:0] n_ae4_0 = n_ae4_0_t2[7:0];
  wire [0:0] n_b_rel4_5_0 = ($signed({{2{1'b0}}, n_ae4_0}) > $signed({{7{1'b0}}, n_s4_5_0})) ? 1'b1 : 1'b0;
  wire [0:0] n_B_0 = n_b_rel3_4_0;
  wire [0:0] n_B_1 = n_b_rel4_5_0;
  wire [6:0] n_pF_0 = i_p_0;
  wire [6:0] n_pF_1 = i_p_0;
  wire [0:0] n_V_0 = ($signed({{2{1'b0}}, n_pF_0}) >= $signed(9'd3)) ? 1'b1 : 1'b0;
  wire [0:0] n_V_1 = ($signed({{2{1'b0}}, n_pF_1}) >= $signed(9'd4)) ? 1'b1 : 1'b0;
  wire [0:0] n_BV_0 = n_B_0;
  wire [0:0] n_BV_1 = n_B_1;
  wire [0:0] n_BV_2 = n_V_0;
  wire [0:0] n_BV_3 = n_V_1;
  wire [3:0] n_G_0_t3 = 4'b1000;
  wire [0:0] n_G_0 = n_G_0_t3[{n_BV_2, n_BV_0}];
  wire [3:0] n_G_1_t4 = 4'b1000;
  wire [0:0] n_G_1 = n_G_1_t4[{n_BV_3, n_BV_1}];
  wire [7:0] n_cnt_0 = {{1{1'b0}}, i_c_0} + {{7{1'b0}}, n_G_0};
  wire [7:0] n_cnt_1 = {{1{1'b0}}, i_c_1} + {{7{1'b0}}, n_G_1};
  wire [0:0] n_done_0 = ($signed({{2{1'b0}}, i_p_0}) == $signed(9'd127)) ? 1'b1 : 1'b0;
  wire [7:0] n_kdone_0 = ({{7{1'b0}}, n_done_0} << 7);
  wire [8:0] n_cr_0 = {{1{1'b0}}, n_cnt_0} - {{1{1'b0}}, n_kdone_0};
  wire [8:0] n_cr_1 = {{1{1'b0}}, n_cnt_1} - {{1{1'b0}}, n_kdone_0};
  wire [6:0] n_c_next_0 = ($signed({{1{n_cr_0[8]}}, n_cr_0}) < $signed(10'd0)) ? 7'd0 : ($signed({{1{n_cr_0[8]}}, n_cr_0}) > $signed(10'd127)) ? 7'd127 : n_cr_0[6:0];
  wire [6:0] n_c_next_1 = ($signed({{1{n_cr_1[8]}}, n_cr_1}) < $signed(10'd0)) ? 7'd0 : ($signed({{1{n_cr_1[8]}}, n_cr_1}) > $signed(10'd127)) ? 7'd127 : n_cr_1[6:0];
  wire [6:0] n_pd_0 = i_p_0;
  wire [0:0] n_pd_1 = n_done_0;
  wire [8:0] n_p1_0 = 9'd1 + {{2{1'b0}}, n_pd_0} - ({{8{1'b0}}, n_pd_1} << 7);
  wire [6:0] n_p_next_0 = ($signed({{1{n_p1_0[8]}}, n_p1_0}) < $signed(10'd0)) ? 7'd0 : ($signed({{1{n_p1_0[8]}}, n_p1_0}) > $signed(10'd127)) ? 7'd127 : n_p1_0[6:0];
  wire [7:0] n_hs_0 = i_h_0;
  wire [7:0] n_hs_1 = i_h_1;
  wire [7:0] n_hs_2 = i_h_2;
  wire [7:0] n_h_next_0 = i_x_0;
  wire [7:0] n_h_next_1 = n_hs_0;
  wire [7:0] n_h_next_2 = n_hs_1;
  wire [7:0] n_h_next_3 = n_hs_2;
  wire [7:0] n_c01_0 = n_cnt_0;
  wire [7:0] n_c01_1 = n_cnt_1;
  wire [0:0] n_ge2_0 = ($signed({{2{1'b0}}, n_c01_0}) >= $signed(10'd74)) ? 1'b1 : 1'b0;
  wire [0:0] n_ge2_1 = ($signed({{2{1'b0}}, n_c01_1}) >= $signed(10'd96)) ? 1'b1 : 1'b0;
  wire [3:0] n_r_0_t5 = 4'b1000;
  wire [0:0] n_r_0 = n_r_0_t5[{n_ge2_1, n_ge2_0}];
  wire [0:0] n_rd_0 = n_r_0;
  wire [0:0] n_rd_1 = n_done_0;
  wire [3:0] n_af_0_t6 = 4'b1000;
  wire [0:0] n_af_0 = n_af_0_t6[{n_rd_1, n_rd_0}];
  assign af = n_af_0;
  assign done = n_done_0;
  assign h_next = {n_h_next_3, n_h_next_2, n_h_next_1, n_h_next_0};
  assign c_next = {n_c_next_1, n_c_next_0};
  assign p_next = n_p_next_0;
endmodule

// Clocked AF detector: lab-generated next-state core chip_1e554783d832 plus the state registers.
module afseq_r2_chip (
  input wire clk,
  input wire rst_n,
  input wire start,
  input wire valid,
  input wire [7:0] rr,
  output reg af,
  output reg done
);
  reg [31:0] h_r;
  wire [31:0] h_c;
  reg [13:0] c_r;
  wire [13:0] c_c;
  reg [6:0] p_r;
  wire [6:0] p_c;
  wire [0:0] af_c;
  wire [0:0] done_c;
  chip_1e554783d832 core (.x(rr), .h(h_r), .c(c_r), .p(p_r), .af(af_c), .done(done_c), .h_next(h_c), .c_next(c_c), .p_next(p_c));
  always @(posedge clk) begin
    if (!rst_n || start) begin
      h_r <= 32'd0; c_r <= 14'd0; p_r <= 7'd0; af <= 1'b0; done <= 1'b0;
    end else if (valid) begin
      h_r <= h_c; c_r <= c_c; p_r <= p_c; af <= af_c[0]; done <= done_c[0];
    end
  end
endmodule
