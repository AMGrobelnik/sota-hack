// Clocked AF detector: lab-generated next-state core chip_7f49487fa312 plus the state registers.
module afseq_r1_and2 (
  input wire clk,
  input wire rst_n,
  input wire start,
  input wire valid,
  input wire [7:0] rr,
  output reg af,
  output reg done
);
  reg [23:0] h_r;
  wire [23:0] h_c;
  reg [13:0] c_r;
  wire [13:0] c_c;
  reg [6:0] p_r;
  wire [6:0] p_c;
  wire [0:0] af_c;
  wire [0:0] done_c;
  chip_7f49487fa312 core (.x(rr), .h(h_r), .c(c_r), .p(p_r), .af(af_c), .done(done_c), .h_next(h_c), .c_next(c_c), .p_next(p_c));
  always @(posedge clk) begin
    if (!rst_n || start) begin
      h_r <= 24'd0; c_r <= 14'd0; p_r <= 7'd0; af <= 1'b0; done <= 1'b0;
    end else if (valid) begin
      h_r <= h_c; c_r <= c_c; p_r <= p_c; af <= af_c[0]; done <= done_c[0];
    end
  end
endmodule
