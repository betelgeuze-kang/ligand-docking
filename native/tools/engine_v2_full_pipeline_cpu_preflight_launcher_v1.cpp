#include <cerrno>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <string_view>
#include <vector>

#include <fcntl.h>
#include <sys/prctl.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

namespace {

constexpr char kLauncherPath[] =
    "/usr/local/libexec/betelgeuze-engine-v2-full-pipeline-cpu-preflight-"
    "launcher-v1";
constexpr char kDynamicLoader[] =
    "/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2";
constexpr char kPythonExecutable[] = "/usr/bin/python3.10";
constexpr char kLibraryPath[] =
    "/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu";
constexpr char kPreloadPaths[] =
    "/usr/lib/x86_64-linux-gnu/libstdc++.so.6.0.30:"
    "/usr/lib/x86_64-linux-gnu/libgcc_s.so.1:"
    "/usr/lib/x86_64-linux-gnu/libpthread.so.0:"
    "/usr/lib/x86_64-linux-gnu/libm.so.6:"
    "/usr/lib/x86_64-linux-gnu/libdl.so.2:"
    "/usr/lib/x86_64-linux-gnu/libc.so.6";
constexpr char kExpectedPreflightSha256[] =
    "2369cfc52596a083964d1ec97f4a675056fdbfc76b4cc8a51db43393d50378e4";
constexpr char kInitialUserNamespace[] = "user:[4026531837]";
constexpr char kInitialMountNamespace[] = "mnt:[4026531841]";
constexpr char kStage0Source[] = R"ENGINEV2STAGE0(import fcntl
import hashlib
import os
import stat
import sys

trusted_launcher_path = "/usr/local/libexec/betelgeuze-engine-v2-full-pipeline-cpu-preflight-launcher-v1"
parent_pid = os.getppid()
try:
    parent_executable = os.readlink(f"/proc/{parent_pid}/exe")
except OSError as exc:
    raise RuntimeError("exact-loader stage0 trusted parent is unavailable") from exc
if parent_pid <= 1 or parent_executable != trusted_launcher_path:
    raise RuntimeError("exact-loader stage0 requires the trusted launcher parent")
def namespace_map(path):
    flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
    if getattr(os, "O_NOFOLLOW", 0) == 0:
        raise RuntimeError("exact-loader stage0 namespace-map no-follow is unavailable")
    descriptor = os.open(path, flags)
    try:
        raw = os.read(descriptor, 4097)
    finally:
        os.close(descriptor)
    try:
        rows = [tuple(int(value, 10) for value in line.split()) for line in raw.decode("ascii").splitlines()]
    except (UnicodeError, ValueError) as exc:
        raise RuntimeError("exact-loader stage0 namespace map is malformed") from exc
    return rows
if (
    namespace_map("/proc/self/uid_map") != [(0, 0, 4294967295)]
    or namespace_map("/proc/self/gid_map") != [(0, 0, 4294967295)]
    or os.readlink("/proc/self/ns/user") != "user:[4026531837]"
    or os.readlink("/proc/self/ns/mnt") != "mnt:[4026531841]"
):
    raise RuntimeError("exact-loader stage0 requires initial host user/mount namespaces")
if len(sys.argv) < 2:
    raise RuntimeError("exact-loader stage0 arguments are incomplete")
source_path = sys.argv[1]
expected_sha256 = "2369cfc52596a083964d1ec97f4a675056fdbfc76b4cc8a51db43393d50378e4"
forwarded_arguments = sys.argv[2:]
if (
    not os.path.isabs(source_path)
    or os.path.basename(source_path)
    != "preflight_engine_v2_full_pipeline_cpu_performance_v1_activation.py"
    or len(expected_sha256) != 64
    or any(character not in "0123456789abcdef" for character in expected_sha256)
):
    raise RuntimeError("exact-loader stage0 source identity is invalid")
source_flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
if getattr(os, "O_NOFOLLOW", 0) == 0:
    raise RuntimeError("exact-loader stage0 no-follow reads are unavailable")
source_descriptor = os.open(source_path, source_flags)
try:
    before = os.fstat(source_descriptor)
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_uid != os.geteuid()
        or before.st_gid != os.getegid()
        or before.st_mode & stat.S_IWOTH
        or before.st_nlink != 1
        or not 1 <= before.st_size <= 4 * 1024 * 1024
    ):
        raise RuntimeError("exact-loader stage0 source is uncontrolled")
    chunks = []
    observed = 0
    while observed <= 4 * 1024 * 1024:
        chunk = os.read(source_descriptor, min(1 << 20, 4 * 1024 * 1024 + 1 - observed))
        if not chunk:
            break
        chunks.append(chunk)
        observed += len(chunk)
    after = os.fstat(source_descriptor)
    identity_fields = (
        "st_dev",
        "st_ino",
        "st_mode",
        "st_uid",
        "st_gid",
        "st_nlink",
        "st_size",
        "st_mtime_ns",
        "st_ctime_ns",
    )
    if observed != before.st_size or any(
        getattr(before, field) != getattr(after, field) for field in identity_fields
    ):
        raise RuntimeError("exact-loader stage0 source changed while read")
    raw = b"".join(chunks)
finally:
    os.close(source_descriptor)
if hashlib.sha256(raw).hexdigest() != expected_sha256:
    raise RuntimeError("exact-loader stage0 source digest changed")
snapshot_descriptor = os.memfd_create(
    "engine-v2-preflight-bootstrap-v1",
    flags=os.MFD_ALLOW_SEALING,
)
try:
    written = 0
    while written < len(raw):
        count = os.write(snapshot_descriptor, raw[written:])
        if count <= 0:
            raise RuntimeError("exact-loader stage0 snapshot write did not progress")
        written += count
    os.fchmod(snapshot_descriptor, 0o400)
    required_seals = (
        fcntl.F_SEAL_SEAL
        | fcntl.F_SEAL_SHRINK
        | fcntl.F_SEAL_GROW
        | fcntl.F_SEAL_WRITE
    )
    fcntl.fcntl(snapshot_descriptor, fcntl.F_ADD_SEALS, required_seals)
    if fcntl.fcntl(snapshot_descriptor, fcntl.F_GET_SEALS) != required_seals:
        raise RuntimeError("exact-loader stage0 snapshot seals changed")
except BaseException:
    os.close(snapshot_descriptor)
    raise
snapshot_path = f"/proc/self/fd/{snapshot_descriptor}"
namespace = {
    "__name__": "__main__",
    "__file__": snapshot_path,
    "__package__": None,
    "__cached__": None,
    "__engine_v2_bootstrap_source_path__": source_path,
    "__engine_v2_bootstrap_expected_sha256__": expected_sha256,
    "__engine_v2_bootstrap_snapshot_fd__": snapshot_descriptor,
}
sys.argv = [snapshot_path, *forwarded_arguments]
exec(
    compile(raw, snapshot_path, "exec", dont_inherit=True, optimize=0),
    namespace,
    namespace,
)
)ENGINEV2STAGE0";

[[noreturn]] void fail(const std::string_view message) {
    std::cerr << "Engine V2 trusted preflight launcher rejected execution: "
              << message << '\n';
    std::exit(125);
}

std::string read_small_file(const char* path) {
    const int descriptor = open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (descriptor < 0) {
        fail("namespace map is unavailable");
    }
    std::vector<char> buffer(4097, '\0');
    const ssize_t observed = read(descriptor, buffer.data(), buffer.size());
    const int saved_errno = errno;
    if (close(descriptor) != 0) {
        fail("namespace-map descriptor close failed");
    }
    errno = saved_errno;
    if (observed <= 0 || static_cast<std::size_t>(observed) >= buffer.size()) {
        fail("namespace map is empty or exceeds its envelope");
    }
    return std::string(buffer.data(), static_cast<std::size_t>(observed));
}

std::string read_link(const char* path) {
    std::vector<char> buffer(4096, '\0');
    const ssize_t observed = readlink(path, buffer.data(), buffer.size() - 1);
    if (observed <= 0 || static_cast<std::size_t>(observed) >= buffer.size() - 1) {
        fail("kernel identity symlink is unavailable");
    }
    return std::string(buffer.data(), static_cast<std::size_t>(observed));
}

void require_initial_host_namespaces() {
    const auto require_full_identity_map = [](const std::string& raw) {
        unsigned long long inside = 1;
        unsigned long long outside = 1;
        unsigned long long length = 0;
        char trailing = '\0';
        return std::sscanf(
                   raw.c_str(), " %llu %llu %llu %c", &inside, &outside, &length,
                   &trailing) == 3 &&
               inside == 0 && outside == 0 && length == 4294967295ULL;
    };
    if (!require_full_identity_map(read_small_file("/proc/self/uid_map")) ||
        !require_full_identity_map(read_small_file("/proc/self/gid_map")) ||
        read_link("/proc/self/ns/user") != kInitialUserNamespace ||
        read_link("/proc/self/ns/mnt") != kInitialMountNamespace) {
        fail("initial host user/mount namespace identity changed");
    }
}

void harden_process() {
    if (prctl(PR_SET_DUMPABLE, 0, 0, 0, 0) != 0) {
        fail("PR_SET_DUMPABLE failed");
    }
    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0) {
        fail("PR_SET_NO_NEW_PRIVS failed");
    }
    sigset_t empty_mask;
    if (sigemptyset(&empty_mask) != 0 ||
        sigprocmask(SIG_SETMASK, &empty_mask, nullptr) != 0) {
        fail("signal-mask reset failed");
    }
    for (int signal_number = 1; signal_number < NSIG; ++signal_number) {
        if (signal_number == SIGKILL || signal_number == SIGSTOP) {
            continue;
        }
        struct sigaction action {};
        action.sa_handler = SIG_DFL;
        if (sigemptyset(&action.sa_mask) != 0 ||
            sigaction(signal_number, &action, nullptr) != 0) {
            if (errno != EINVAL) {
                fail("signal disposition reset failed");
            }
        }
    }
    umask(077);
    if (chdir("/") != 0) {
        fail("root working-directory selection failed");
    }
#if defined(SYS_close_range)
    if (syscall(SYS_close_range, 3U, ~0U, 0U) != 0) {
        fail("inherited descriptor closure failed");
    }
#else
    fail("close_range is unavailable");
#endif
    if (clearenv() != 0 || setenv("CUDA_VISIBLE_DEVICES", "", 1) != 0 ||
        setenv("HIP_VISIBLE_DEVICES", "", 1) != 0 ||
        setenv("LC_ALL", "C", 1) != 0 ||
        setenv("PATH", "/usr/bin:/bin", 1) != 0 ||
        setenv("ROCR_VISIBLE_DEVICES", "", 1) != 0) {
        fail("environment normalization failed");
    }
}

std::string self_executable() {
    return read_link("/proc/self/exe");
}

bool valid_source_path(const std::string_view path) {
    constexpr std::string_view basename =
        "preflight_engine_v2_full_pipeline_cpu_performance_v1_activation.py";
    return !path.empty() && path.front() == '/' && path.size() > basename.size() &&
           path.substr(path.size() - basename.size()) == basename &&
           path[path.size() - basename.size() - 1] == '/';
}

int propagate_child_status(const pid_t child) {
    int status = 0;
    while (waitpid(child, &status, 0) < 0) {
        if (errno != EINTR) {
            fail("child wait failed");
        }
    }
    if (WIFEXITED(status)) {
        return WEXITSTATUS(status);
    }
    if (WIFSIGNALED(status)) {
        return 128 + WTERMSIG(status);
    }
    return 125;
}

}  // namespace

int main(int argc, char** argv) {
    harden_process();
    require_initial_host_namespaces();
    if (self_executable() != kLauncherPath) {
        fail("launcher is not executing from its root-provisioned path");
    }
    if (argc < 4 || std::string_view(argv[0]) != kLauncherPath ||
        std::string_view(argv[2]) != "--" ||
        !valid_source_path(argv[1])) {
        fail("expected SOURCE -- ARGS launcher protocol");
    }
    if (std::strlen(kExpectedPreflightSha256) != 64 ||
        std::string_view(kStage0Source).find(kExpectedPreflightSha256) ==
            std::string_view::npos) {
        fail("compiled bootstrap identity is malformed");
    }

    const pid_t launcher_pid = getpid();
    const pid_t child = fork();
    if (child < 0) {
        fail("fork failed");
    }
    if (child == 0) {
        if (prctl(PR_SET_PDEATHSIG, SIGKILL, 0, 0, 0) != 0 ||
            getppid() != launcher_pid) {
            _exit(125);
        }
        std::vector<char*> arguments = {
            const_cast<char*>(kDynamicLoader),
            const_cast<char*>("--inhibit-cache"),
            const_cast<char*>("--library-path"),
            const_cast<char*>(kLibraryPath),
            const_cast<char*>("--glibc-hwcaps-mask"),
            const_cast<char*>(""),
            const_cast<char*>("--preload"),
            const_cast<char*>(kPreloadPaths),
            const_cast<char*>("--argv0"),
            const_cast<char*>(kPythonExecutable),
            const_cast<char*>(kPythonExecutable),
            const_cast<char*>("-I"),
            const_cast<char*>("-S"),
            const_cast<char*>("-B"),
            const_cast<char*>("-c"),
            const_cast<char*>(kStage0Source),
            argv[1],
        };
        for (int index = 3; index < argc; ++index) {
            arguments.push_back(argv[index]);
        }
        arguments.push_back(nullptr);
        char cuda[] = "CUDA_VISIBLE_DEVICES=";
        char hip[] = "HIP_VISIBLE_DEVICES=";
        char locale[] = "LC_ALL=C";
        char path[] = "PATH=/usr/bin:/bin";
        char rocr[] = "ROCR_VISIBLE_DEVICES=";
        char* environment[] = {cuda, hip, locale, path, rocr, nullptr};
        execve(kDynamicLoader, arguments.data(), environment);
        _exit(125);
    }
    return propagate_child_status(child);
}
