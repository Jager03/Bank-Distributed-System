
namespace py rpc

struct TransferRequest{
    1: i32 ID
    2: double amount
}

service Bank{
    bool transferMoney(1:TransferRequest request)
    double cancelTransfer(1:i32 ID)
}