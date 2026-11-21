from chiplab.verify.sandbox import screen


def test_screen_rejects_system_tasks_and_includes():
    assert screen('module m; initial $system("rm -rf ~"); endmodule')
    assert screen('module m; initial $readmemh("/etc/passwd", mem); endmodule')
    assert screen('`include "/etc/shadow"\nmodule m; endmodule')
    assert screen('module m; initial $dumpfile("x.vcd"); endmodule')


def test_screen_allows_plain_rtl():
    assert screen("module m(input [3:0] a, output [4:0] y); assign y = $signed(a) + $unsigned(a); endmodule") == []
    assert screen("// $system in a comment is fine\nmodule m; endmodule") == []
