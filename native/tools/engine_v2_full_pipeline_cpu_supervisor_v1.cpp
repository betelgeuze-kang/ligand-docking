#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <grp.h>
#include <linux/memfd.h>
#include <linux/nsfs.h>
#include <poll.h>
#include <sched.h>
#include <signal.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/prctl.h>
#include <sys/ptrace.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <sys/un.h>
#include <sys/wait.h>
#include <unistd.h>

#include <algorithm>
#include <array>
#include <chrono>
#include <cctype>
#include <cstddef>
#include <cstdio>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <limits>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#ifndef SO_PEERPIDFD
#define SO_PEERPIDFD 77
#endif

namespace {

constexpr char kSupervisorId[] =
    "engine_v2_full_pipeline_cpu_supervisor_v1";
constexpr char kSocketPath[] =
    "/run/betelgeuze-engine-v2/full-pipeline-cpu-supervisor-v1.sock";
constexpr char kDynamicLoaderPath[] =
    "/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2";
constexpr char kPythonExecutablePath[] = "/usr/bin/python3.10";
constexpr char kDynamicLoaderLibraryPath[] =
    "/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu";
constexpr char kPreloadPaths[] =
    "/usr/lib/x86_64-linux-gnu/libstdc++.so.6.0.30:"
    "/usr/lib/x86_64-linux-gnu/libgcc_s.so.1:"
    "/usr/lib/x86_64-linux-gnu/libpthread.so.0:"
    "/usr/lib/x86_64-linux-gnu/libm.so.6:"
    "/usr/lib/x86_64-linux-gnu/libdl.so.2:"
    "/usr/lib/x86_64-linux-gnu/libc.so.6";

constexpr char kActivationSha256[] =
    "0c282c168e201eea5ac9315f50d1fd49aa2d825804d1f03b89602c5cbae21325";
#ifndef BETELGEUZE_ENGINE_V2_SUPERVISOR_PREFLIGHT_SHA256
#define BETELGEUZE_ENGINE_V2_SUPERVISOR_PREFLIGHT_SHA256 \
  "1c50fa1b3bb183f63070873840a53a648e810a3240ff1829e2a49cca8373bdb5"
#endif
constexpr char kPreflightSha256[] =
    BETELGEUZE_ENGINE_V2_SUPERVISOR_PREFLIGHT_SHA256;
constexpr char kProfileSha256[] =
    "385fb713cca8f39353f138115749abdfc9768b02222e13111a418360be30a000";
constexpr char kRuntimeManifestSha256[] =
    "72b90f500af43c921ce0b8f7d6774c5e99a7e4f3fe366478b3fc33b524b4b404";
constexpr char kDynamicLoaderSha256[] =
    "8d06f393f4a93bcf9b81145a259524d66a95522a646bf8d7e05b6ffdf2e63dcc";
constexpr char kPythonExecutableSha256[] =
    "7d51cd6b48b521277f5caa4610a82126e315fa2be4df069823a8b1eeb5bd4a86";
constexpr char kLaunchVectorSha256[] =
    "3844da69d7b4a1dd61cde9ffa559c7409a6d23b43a80f63dcea612f859a932d3";
constexpr char kLaunchEnvironmentSha256[] =
    "5cf4cf74eba4f493ae3f8a88c3459e2f8861146b6e38b5c4d7bd65e958f0da96";

// A separately reviewed package may compile an exact non-root client roster
// into the binary.  The default build remains unrostered, and neither roster
// definition can change the three false authority constants below.  This
// source cannot be activated by an environment variable, runtime command-line
// flag, or caller-controlled file.
#ifndef BETELGEUZE_ENGINE_V2_SUPERVISOR_CLIENT_UID
#define BETELGEUZE_ENGINE_V2_SUPERVISOR_CLIENT_UID \
  std::numeric_limits<uid_t>::max()
#endif
#ifndef BETELGEUZE_ENGINE_V2_SUPERVISOR_CLIENT_GID
#define BETELGEUZE_ENGINE_V2_SUPERVISOR_CLIENT_GID \
  std::numeric_limits<gid_t>::max()
#endif
constexpr bool kInstallationAuthorized = false;
constexpr bool kRuntimeLaunchAuthorized = false;
constexpr bool kQualificationConsumptionAuthorized = false;
constexpr uid_t kExpectedClientUid =
    BETELGEUZE_ENGINE_V2_SUPERVISOR_CLIENT_UID;
constexpr gid_t kExpectedClientGid =
    BETELGEUZE_ENGINE_V2_SUPERVISOR_CLIENT_GID;
constexpr ino_t kExpectedInitialUserNamespaceInode = 4026531837;
constexpr ino_t kExpectedInitialMountNamespaceInode = 4026531841;

constexpr std::size_t kDigestBytes = 32;
constexpr std::size_t kNonceBytes = 32;
constexpr std::size_t kRequiredRequestFds = 3;
constexpr std::size_t kMaximumSourceBytes = 4U * 1024U * 1024U;
constexpr std::size_t kMaximumExecutableBytes = 32U * 1024U * 1024U;
constexpr uint32_t kMaximumTimeoutSeconds = 900;
constexpr int kSnapshotFd = 190;
constexpr int kArtifactDirectoryFd = 191;
constexpr int kRuntimeDirectoryFd = 192;
constexpr int kHandoffSocketFd = 193;
constexpr int kLoaderFd = 194;
constexpr int kPythonFd = 195;
constexpr unsigned int kFirstClosedFd = 3;
constexpr unsigned int kLastLowClosedFd = 189;
constexpr unsigned int kFirstHighClosedFd = 196;
constexpr char kRequestMagic[16] = "BGV2CPUSUPREQ1";
constexpr char kHandoffMagic[16] = "BGV2CPUHANDOF1";
constexpr char kTerminalMagic[16] = "BGV2CPUTERMV1";
constexpr uint32_t kProtocolVersion = 1;
constexpr uint32_t kRequestFlagNone = 0;
constexpr uint32_t kHandoffFlagExecObserved = 1U << 0U;
constexpr uint32_t kHandoffFlagPeerCredentialBound = 1U << 1U;
constexpr uint32_t kHandoffFlagNamespaceFdsBound = 1U << 2U;
constexpr uint32_t kTerminalFlagTimedOut = 1U << 0U;
constexpr uint32_t kTerminalFlagContainmentFailure = 1U << 1U;

#pragma pack(push, 1)
struct RequestWireV1 {
  char magic[16];
  uint32_t version_be;
  uint32_t size_be;
  std::array<uint8_t, kNonceBytes> nonce;
  std::array<uint8_t, kDigestBytes> activation_sha256;
  std::array<uint8_t, kDigestBytes> preflight_sha256;
  std::array<uint8_t, kDigestBytes> profile_sha256;
  std::array<uint8_t, kDigestBytes> runtime_manifest_sha256;
  uint32_t flags_be;
  uint32_t timeout_seconds_be;
};

struct HandoffWireV1 {
  char magic[16];
  uint32_t version_be;
  uint32_t size_be;
  std::array<uint8_t, kNonceBytes> nonce;
  std::array<uint8_t, kDigestBytes> request_sha256;
  std::array<uint8_t, kDigestBytes> activation_sha256;
  std::array<uint8_t, kDigestBytes> preflight_sha256;
  std::array<uint8_t, kDigestBytes> profile_sha256;
  std::array<uint8_t, kDigestBytes> runtime_manifest_sha256;
  std::array<uint8_t, kDigestBytes> source_snapshot_sha256;
  std::array<uint8_t, kDigestBytes> dynamic_loader_sha256;
  std::array<uint8_t, kDigestBytes> python_executable_sha256;
  std::array<uint8_t, kDigestBytes> supervisor_binary_sha256;
  std::array<uint8_t, kDigestBytes> launch_vector_sha256;
  std::array<uint8_t, kDigestBytes> launch_environment_sha256;
  uint32_t peer_pid_be;
  uint32_t peer_uid_be;
  uint32_t peer_gid_be;
  uint32_t child_pid_be;
  uint64_t user_namespace_device_be;
  uint64_t user_namespace_inode_be;
  uint64_t mount_namespace_device_be;
  uint64_t mount_namespace_inode_be;
  uint32_t flags_be;
  uint32_t reserved_be;
};

struct TerminalWireV1 {
  char magic[16];
  uint32_t version_be;
  uint32_t size_be;
  std::array<uint8_t, kNonceBytes> nonce;
  std::array<uint8_t, kDigestBytes> request_sha256;
  uint32_t exit_code_be;
  uint32_t flags_be;
};
#pragma pack(pop)

static_assert(sizeof(RequestWireV1) == 192);
static_assert(sizeof(HandoffWireV1) == 464);
static_assert(sizeof(TerminalWireV1) == 96);
static_assert(!kInstallationAuthorized);
static_assert(!kRuntimeLaunchAuthorized);
static_assert(!kQualificationConsumptionAuthorized);

class UniqueFd {
 public:
  UniqueFd() = default;
  explicit UniqueFd(int value) : value_(value) {}
  ~UniqueFd() {
    if (value_ >= 0) {
      (void)::close(value_);
    }
  }
  UniqueFd(const UniqueFd&) = delete;
  UniqueFd& operator=(const UniqueFd&) = delete;
  UniqueFd(UniqueFd&& other) noexcept : value_(std::exchange(other.value_, -1)) {}
  UniqueFd& operator=(UniqueFd&& other) noexcept {
    if (this != &other) {
      if (value_ >= 0) {
        (void)::close(value_);
      }
      value_ = std::exchange(other.value_, -1);
    }
    return *this;
  }
  [[nodiscard]] int get() const { return value_; }
  [[nodiscard]] bool valid() const { return value_ >= 0; }
  int release() { return std::exchange(value_, -1); }

 private:
  int value_ = -1;
};

[[noreturn]] void fail(const std::string& message) {
  throw std::runtime_error(message);
}

std::string errno_message(const char* operation) {
  return std::string(operation) + ": " + std::strerror(errno);
}

uint64_t host_to_big_u64(uint64_t value) {
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
  return __builtin_bswap64(value);
#else
  return value;
#endif
}

class Sha256 {
 public:
  Sha256() { reset(); }

  void update(const uint8_t* data, std::size_t size) {
    for (std::size_t index = 0; index < size; ++index) {
      block_[block_size_++] = data[index];
      if (block_size_ == block_.size()) {
        transform();
        bit_count_ += 512;
        block_size_ = 0;
      }
    }
  }

  std::array<uint8_t, kDigestBytes> finish() {
    const uint64_t total_bits = bit_count_ + block_size_ * 8U;
    block_[block_size_++] = 0x80U;
    if (block_size_ > 56U) {
      while (block_size_ < block_.size()) {
        block_[block_size_++] = 0;
      }
      transform();
      block_size_ = 0;
    }
    while (block_size_ < 56U) {
      block_[block_size_++] = 0;
    }
    for (int shift = 56; shift >= 0; shift -= 8) {
      block_[block_size_++] = static_cast<uint8_t>(total_bits >> shift);
    }
    transform();
    std::array<uint8_t, kDigestBytes> result{};
    for (std::size_t index = 0; index < state_.size(); ++index) {
      result[index * 4U] = static_cast<uint8_t>(state_[index] >> 24U);
      result[index * 4U + 1U] = static_cast<uint8_t>(state_[index] >> 16U);
      result[index * 4U + 2U] = static_cast<uint8_t>(state_[index] >> 8U);
      result[index * 4U + 3U] = static_cast<uint8_t>(state_[index]);
    }
    reset();
    return result;
  }

 private:
  static constexpr std::array<uint32_t, 64> kRound = {
      0x428a2f98U, 0x71374491U, 0xb5c0fbcfU, 0xe9b5dba5U, 0x3956c25bU,
      0x59f111f1U, 0x923f82a4U, 0xab1c5ed5U, 0xd807aa98U, 0x12835b01U,
      0x243185beU, 0x550c7dc3U, 0x72be5d74U, 0x80deb1feU, 0x9bdc06a7U,
      0xc19bf174U, 0xe49b69c1U, 0xefbe4786U, 0x0fc19dc6U, 0x240ca1ccU,
      0x2de92c6fU, 0x4a7484aaU, 0x5cb0a9dcU, 0x76f988daU, 0x983e5152U,
      0xa831c66dU, 0xb00327c8U, 0xbf597fc7U, 0xc6e00bf3U, 0xd5a79147U,
      0x06ca6351U, 0x14292967U, 0x27b70a85U, 0x2e1b2138U, 0x4d2c6dfcU,
      0x53380d13U, 0x650a7354U, 0x766a0abbU, 0x81c2c92eU, 0x92722c85U,
      0xa2bfe8a1U, 0xa81a664bU, 0xc24b8b70U, 0xc76c51a3U, 0xd192e819U,
      0xd6990624U, 0xf40e3585U, 0x106aa070U, 0x19a4c116U, 0x1e376c08U,
      0x2748774cU, 0x34b0bcb5U, 0x391c0cb3U, 0x4ed8aa4aU, 0x5b9cca4fU,
      0x682e6ff3U, 0x748f82eeU, 0x78a5636fU, 0x84c87814U, 0x8cc70208U,
      0x90befffaU, 0xa4506cebU, 0xbef9a3f7U, 0xc67178f2U};

  static uint32_t rotate_right(uint32_t value, uint32_t count) {
    return (value >> count) | (value << (32U - count));
  }

  void reset() {
    state_ = {0x6a09e667U, 0xbb67ae85U, 0x3c6ef372U, 0xa54ff53aU,
              0x510e527fU, 0x9b05688cU, 0x1f83d9abU, 0x5be0cd19U};
    block_.fill(0);
    bit_count_ = 0;
    block_size_ = 0;
  }

  void transform() {
    std::array<uint32_t, 64> words{};
    for (std::size_t index = 0; index < 16U; ++index) {
      const std::size_t offset = index * 4U;
      words[index] = (static_cast<uint32_t>(block_[offset]) << 24U) |
                     (static_cast<uint32_t>(block_[offset + 1U]) << 16U) |
                     (static_cast<uint32_t>(block_[offset + 2U]) << 8U) |
                     static_cast<uint32_t>(block_[offset + 3U]);
    }
    for (std::size_t index = 16U; index < words.size(); ++index) {
      const uint32_t s0 = rotate_right(words[index - 15U], 7U) ^
                          rotate_right(words[index - 15U], 18U) ^
                          (words[index - 15U] >> 3U);
      const uint32_t s1 = rotate_right(words[index - 2U], 17U) ^
                          rotate_right(words[index - 2U], 19U) ^
                          (words[index - 2U] >> 10U);
      words[index] = words[index - 16U] + s0 + words[index - 7U] + s1;
    }
    uint32_t a = state_[0];
    uint32_t b = state_[1];
    uint32_t c = state_[2];
    uint32_t d = state_[3];
    uint32_t e = state_[4];
    uint32_t f = state_[5];
    uint32_t g = state_[6];
    uint32_t h = state_[7];
    for (std::size_t index = 0; index < words.size(); ++index) {
      const uint32_t upper = rotate_right(e, 6U) ^ rotate_right(e, 11U) ^
                             rotate_right(e, 25U);
      const uint32_t choose = (e & f) ^ ((~e) & g);
      const uint32_t first = h + upper + choose + kRound[index] + words[index];
      const uint32_t lower = rotate_right(a, 2U) ^ rotate_right(a, 13U) ^
                             rotate_right(a, 22U);
      const uint32_t majority = (a & b) ^ (a & c) ^ (b & c);
      const uint32_t second = lower + majority;
      h = g;
      g = f;
      f = e;
      e = d + first;
      d = c;
      c = b;
      b = a;
      a = first + second;
    }
    state_[0] += a;
    state_[1] += b;
    state_[2] += c;
    state_[3] += d;
    state_[4] += e;
    state_[5] += f;
    state_[6] += g;
    state_[7] += h;
  }

  std::array<uint32_t, 8> state_{};
  std::array<uint8_t, 64> block_{};
  uint64_t bit_count_ = 0;
  std::size_t block_size_ = 0;
};

std::array<uint8_t, kDigestBytes> sha256(const uint8_t* data, std::size_t size) {
  Sha256 digest;
  digest.update(data, size);
  return digest.finish();
}

std::string digest_hex(const std::array<uint8_t, kDigestBytes>& digest) {
  std::ostringstream output;
  output << std::hex << std::setfill('0');
  for (const uint8_t value : digest) {
    output << std::setw(2) << static_cast<unsigned int>(value);
  }
  return output.str();
}

std::array<uint8_t, kDigestBytes> digest_from_hex(const char* value) {
  if (value == nullptr || std::strlen(value) != kDigestBytes * 2U) {
    fail("frozen hexadecimal digest length changed");
  }
  std::array<uint8_t, kDigestBytes> result{};
  for (std::size_t index = 0; index < result.size(); ++index) {
    const auto nibble = [](char character) -> uint8_t {
      if (character >= '0' && character <= '9') {
        return static_cast<uint8_t>(character - '0');
      }
      if (character >= 'a' && character <= 'f') {
        return static_cast<uint8_t>(character - 'a' + 10);
      }
      fail("frozen hexadecimal digest is not lowercase ASCII");
    };
    result[index] = static_cast<uint8_t>(
        (static_cast<unsigned int>(nibble(value[index * 2U])) << 4U) |
        nibble(value[index * 2U + 1U]));
  }
  return result;
}

std::array<std::string, 18> launch_arguments() {
  return {kDynamicLoaderPath,
          "--inhibit-cache",
          "--library-path",
          kDynamicLoaderLibraryPath,
          "--glibc-hwcaps-mask",
          "",
          "--preload",
          kPreloadPaths,
          "--argv0",
          kPythonExecutablePath,
          "/proc/self/fd/195",
          "-I",
          "-S",
          "-B",
          "/proc/self/fd/190",
          "--artifact-directory",
          "/proc/self/fd/191",
          "--runtime-root=/proc/self/fd/192"};
}

std::array<std::string, 9> launch_environment() {
  return {"CUDA_VISIBLE_DEVICES=",
          "HIP_VISIBLE_DEVICES=",
          "LC_ALL=C",
          "PATH=/usr/bin:/bin",
          "ROCR_VISIBLE_DEVICES=",
          "BETELGEUZE_SUPERVISOR_HANDOFF_FD=193",
          "BETELGEUZE_SUPERVISOR_SOURCE_FD=190",
          "BETELGEUZE_SUPERVISOR_ARTIFACT_FD=191",
          "BETELGEUZE_SUPERVISOR_RUNTIME_FD=192"};
}

template <std::size_t Size>
std::array<uint8_t, kDigestBytes> canonical_vector_digest(
    const std::array<std::string, Size>& values) {
  Sha256 digest;
  constexpr uint8_t delimiter = 0;
  for (const std::string& value : values) {
    digest.update(reinterpret_cast<const uint8_t*>(value.data()), value.size());
    digest.update(&delimiter, 1);
  }
  return digest.finish();
}

template <std::size_t Size>
bool exact_magic(const char (&expected)[Size], const char* observed,
                 std::size_t observed_size) {
  static_assert(Size <= 16U);
  return observed_size == 16U &&
         std::memcmp(observed, expected, Size - 1U) == 0 &&
         std::all_of(observed + Size - 1U, observed + observed_size,
                     [](char value) { return value == '\0'; });
}

void require_digest(const std::array<uint8_t, kDigestBytes>& observed,
                    const char* expected, const char* name) {
  if (digest_hex(observed) != expected) {
    fail(std::string(name) + " digest changed");
  }
}

struct FileBytes {
  std::vector<uint8_t> raw;
  struct stat metadata {};
  std::array<uint8_t, kDigestBytes> digest{};
};

bool same_file_identity(const struct stat& left, const struct stat& right) {
  return left.st_dev == right.st_dev && left.st_ino == right.st_ino &&
         left.st_mode == right.st_mode && left.st_uid == right.st_uid &&
         left.st_gid == right.st_gid && left.st_nlink == right.st_nlink &&
         left.st_size == right.st_size && left.st_mtim.tv_sec == right.st_mtim.tv_sec &&
         left.st_mtim.tv_nsec == right.st_mtim.tv_nsec &&
         left.st_ctim.tv_sec == right.st_ctim.tv_sec &&
         left.st_ctim.tv_nsec == right.st_ctim.tv_nsec;
}

FileBytes read_stable_file(int descriptor, std::size_t maximum_bytes,
                           const char* name) {
  FileBytes result;
  struct stat before {};
  if (::fstat(descriptor, &before) != 0) {
    fail(errno_message(name));
  }
  if (!S_ISREG(before.st_mode) || before.st_size <= 0 ||
      static_cast<uint64_t>(before.st_size) > maximum_bytes) {
    fail(std::string(name) + " is not a bounded regular file");
  }
  result.raw.resize(static_cast<std::size_t>(before.st_size));
  std::size_t offset = 0;
  while (offset < result.raw.size()) {
    const ssize_t count = ::pread(descriptor, result.raw.data() + offset,
                                  result.raw.size() - offset,
                                  static_cast<off_t>(offset));
    if (count < 0 && errno == EINTR) {
      continue;
    }
    if (count <= 0) {
      fail(std::string(name) + " changed or ended while read");
    }
    offset += static_cast<std::size_t>(count);
  }
  struct stat after {};
  if (::fstat(descriptor, &after) != 0 || !same_file_identity(before, after)) {
    fail(std::string(name) + " identity changed while read");
  }
  result.metadata = before;
  result.digest = sha256(result.raw.data(), result.raw.size());
  return result;
}

UniqueFd create_sealed_memfd(const char* name, const uint8_t* raw,
                             std::size_t size, mode_t mode) {
  const int descriptor = static_cast<int>(
      ::syscall(SYS_memfd_create, name, MFD_ALLOW_SEALING | MFD_CLOEXEC));
  if (descriptor < 0) {
    fail(errno_message("memfd_create"));
  }
  UniqueFd owner(descriptor);
  std::size_t offset = 0;
  while (offset < size) {
    const ssize_t count = ::write(owner.get(), raw + offset, size - offset);
    if (count < 0 && errno == EINTR) {
      continue;
    }
    if (count <= 0) {
      fail("sealed memfd write did not progress");
    }
    offset += static_cast<std::size_t>(count);
  }
  if (::fchmod(owner.get(), mode) != 0) {
    fail(errno_message("fchmod sealed memfd"));
  }
  const int seals = F_SEAL_SEAL | F_SEAL_SHRINK | F_SEAL_GROW | F_SEAL_WRITE;
  if (::fcntl(owner.get(), F_ADD_SEALS, seals) != 0 ||
      ::fcntl(owner.get(), F_GET_SEALS) != seals) {
    fail(errno_message("seal memfd"));
  }
  return owner;
}

void require_directory_fd(int descriptor, const struct ucred& peer,
                          const char* name) {
  struct stat metadata {};
  if (::fstat(descriptor, &metadata) != 0 || !S_ISDIR(metadata.st_mode) ||
      (metadata.st_uid != peer.uid && metadata.st_uid != 0) ||
      (metadata.st_mode & (S_IWGRP | S_IWOTH)) != 0) {
    fail(std::string(name) + " directory descriptor is uncontrolled");
  }
}

struct NamespaceHandles {
  UniqueFd user;
  UniqueFd mount;
  struct stat user_metadata {};
  struct stat mount_metadata {};
};

void require_namespace_type(int descriptor, int expected, const char* name) {
  const int observed = ::ioctl(descriptor, NS_GET_NSTYPE);
  if (observed != expected) {
    fail(std::string(name) + " namespace type changed");
  }
}

NamespaceHandles open_initial_namespace_handles() {
  NamespaceHandles handles;
  handles.user = UniqueFd(::open("/proc/self/ns/user", O_RDONLY | O_CLOEXEC));
  handles.mount = UniqueFd(::open("/proc/self/ns/mnt", O_RDONLY | O_CLOEXEC));
  if (!handles.user.valid() || !handles.mount.valid()) {
    fail("trusted supervisor namespace handles are unavailable");
  }
  require_namespace_type(handles.user.get(), CLONE_NEWUSER, "user");
  require_namespace_type(handles.mount.get(), CLONE_NEWNS, "mount");
  if (::fstat(handles.user.get(), &handles.user_metadata) != 0 ||
      ::fstat(handles.mount.get(), &handles.mount_metadata) != 0) {
    fail(errno_message("fstat trusted supervisor namespace"));
  }
  uid_t user_namespace_owner = std::numeric_limits<uid_t>::max();
  if (handles.user_metadata.st_ino != kExpectedInitialUserNamespaceInode ||
      handles.mount_metadata.st_ino != kExpectedInitialMountNamespaceInode ||
      ::ioctl(handles.user.get(), NS_GET_OWNER_UID, &user_namespace_owner) != 0 ||
      user_namespace_owner != 0) {
    fail("trusted supervisor is not in the exact initial user/mount namespaces");
  }
  errno = 0;
  const int user_parent = ::ioctl(handles.user.get(), NS_GET_PARENT);
  if (user_parent >= 0) {
    (void)::close(user_parent);
    fail("trusted supervisor user namespace has a parent");
  }
  if (errno != EPERM) {
    fail("trusted supervisor initial user namespace could not be attested");
  }
  UniqueFd mount_owner(::ioctl(handles.mount.get(), NS_GET_USERNS));
  struct stat owner_metadata {};
  if (!mount_owner.valid() || ::fstat(mount_owner.get(), &owner_metadata) != 0 ||
      owner_metadata.st_dev != handles.user_metadata.st_dev ||
      owner_metadata.st_ino != handles.user_metadata.st_ino) {
    fail("trusted supervisor mount namespace owner changed");
  }
  return handles;
}

void require_child_namespace_identity(pid_t child,
                                      const NamespaceHandles& trusted) {
  const std::string prefix = "/proc/" + std::to_string(child) + "/ns/";
  UniqueFd user(::open((prefix + "user").c_str(), O_RDONLY | O_CLOEXEC));
  UniqueFd mount(::open((prefix + "mnt").c_str(), O_RDONLY | O_CLOEXEC));
  struct stat user_metadata {};
  struct stat mount_metadata {};
  if (!user.valid() || !mount.valid() ||
      ::fstat(user.get(), &user_metadata) != 0 ||
      ::fstat(mount.get(), &mount_metadata) != 0 ||
      user_metadata.st_dev != trusted.user_metadata.st_dev ||
      user_metadata.st_ino != trusted.user_metadata.st_ino ||
      mount_metadata.st_dev != trusted.mount_metadata.st_dev ||
      mount_metadata.st_ino != trusted.mount_metadata.st_ino) {
    fail("tracee escaped the trusted initial namespace descriptors");
  }
}

struct ReceivedRequest {
  RequestWireV1 wire{};
  std::array<UniqueFd, kRequiredRequestFds> descriptors;
  struct ucred peer {};
  std::array<uint8_t, kDigestBytes> request_sha256{};
};

ReceivedRequest receive_request(int connection) {
  ReceivedRequest request;
  socklen_t peer_size = sizeof(request.peer);
  if (::getsockopt(connection, SOL_SOCKET, SO_PEERCRED, &request.peer,
                   &peer_size) != 0 ||
      peer_size != sizeof(request.peer) || request.peer.pid <= 1 ||
      request.peer.uid == 0 || request.peer.uid != kExpectedClientUid ||
      request.peer.gid != kExpectedClientGid) {
    fail("request peer is not the independently rostered execution account");
  }

  std::array<char, CMSG_SPACE(sizeof(int) * kRequiredRequestFds)> control{};
  struct iovec vector {
    &request.wire, sizeof(request.wire)
  };
  struct msghdr message {};
  message.msg_iov = &vector;
  message.msg_iovlen = 1;
  message.msg_control = control.data();
  message.msg_controllen = control.size();
  const ssize_t count = ::recvmsg(connection, &message, MSG_CMSG_CLOEXEC);
  if (count != static_cast<ssize_t>(sizeof(request.wire)) ||
      (message.msg_flags & (MSG_TRUNC | MSG_CTRUNC)) != 0) {
    fail("supervisor request packet size or ancillary data changed");
  }
  std::size_t observed_fds = 0;
  for (struct cmsghdr* header = CMSG_FIRSTHDR(&message); header != nullptr;
       header = CMSG_NXTHDR(&message, header)) {
    if (header->cmsg_level != SOL_SOCKET || header->cmsg_type != SCM_RIGHTS ||
        header->cmsg_len != CMSG_LEN(sizeof(int) * kRequiredRequestFds) ||
        observed_fds != 0) {
      fail("supervisor request ancillary message changed");
    }
    const auto* received = reinterpret_cast<const int*>(CMSG_DATA(header));
    for (std::size_t index = 0; index < kRequiredRequestFds; ++index) {
      request.descriptors[index] = UniqueFd(received[index]);
      ++observed_fds;
    }
  }
  if (observed_fds != kRequiredRequestFds) {
    fail("supervisor request requires exactly three descriptors");
  }
  request.request_sha256 = sha256(
      reinterpret_cast<const uint8_t*>(&request.wire), sizeof(request.wire));
  return request;
}

UniqueFd open_socket_peer_pidfd(int connection) {
  int descriptor = -1;
  socklen_t descriptor_size = sizeof(descriptor);
  if (::getsockopt(connection, SOL_SOCKET, SO_PEERPIDFD, &descriptor,
                   &descriptor_size) != 0) {
    fail("request peer pidfd is unavailable");
  }
  UniqueFd owner(descriptor);
  if (descriptor_size != sizeof(descriptor) || !owner.valid()) {
    fail("request peer pidfd is unavailable");
  }
  const int flags = ::fcntl(owner.get(), F_GETFD);
  if (flags < 0 || ::fcntl(owner.get(), F_SETFD, flags | FD_CLOEXEC) != 0) {
    fail("request peer pidfd close-on-exec binding failed");
  }
  return owner;
}

uint32_t validate_request(const ReceivedRequest& request) {
  if (!exact_magic(kRequestMagic, request.wire.magic,
                   sizeof(request.wire.magic)) ||
      ntohl(request.wire.version_be) != kProtocolVersion ||
      ntohl(request.wire.size_be) != sizeof(RequestWireV1) ||
      ntohl(request.wire.flags_be) != kRequestFlagNone) {
    fail("supervisor request header changed");
  }
  if (std::all_of(request.wire.nonce.begin(), request.wire.nonce.end(),
                  [](uint8_t value) { return value == 0; })) {
    fail("supervisor request nonce must be nonzero");
  }
  require_digest(request.wire.activation_sha256, kActivationSha256,
                 "activation");
  require_digest(request.wire.preflight_sha256, kPreflightSha256,
                 "preflight");
  require_digest(request.wire.profile_sha256, kProfileSha256, "profile");
  require_digest(request.wire.runtime_manifest_sha256,
                 kRuntimeManifestSha256, "runtime manifest");
  const uint32_t timeout_seconds = ntohl(request.wire.timeout_seconds_be);
  if (timeout_seconds == 0 || timeout_seconds > kMaximumTimeoutSeconds) {
    fail("supervisor request timeout is outside the frozen envelope");
  }
  require_directory_fd(request.descriptors[1].get(), request.peer,
                       "artifact");
  require_directory_fd(request.descriptors[2].get(), request.peer, "runtime");
  return timeout_seconds;
}

UniqueFd open_exact_root_executable(const char* path, const char* digest,
                                    const char* name) {
  UniqueFd descriptor(::open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW));
  if (!descriptor.valid()) {
    fail(errno_message(name));
  }
  const FileBytes identity =
      read_stable_file(descriptor.get(), kMaximumExecutableBytes, name);
  if (identity.metadata.st_uid != 0 || identity.metadata.st_gid != 0 ||
      (identity.metadata.st_mode & (S_IWGRP | S_IWOTH)) != 0 ||
      digest_hex(identity.digest) != digest) {
    fail(std::string(name) + " root ownership or digest changed");
  }
  return descriptor;
}

UniqueFd open_trusted_null_device() {
  UniqueFd descriptor(::open("/dev/null", O_RDWR | O_CLOEXEC | O_NOFOLLOW));
  struct stat metadata {};
  if (!descriptor.valid() || ::fstat(descriptor.get(), &metadata) != 0 ||
      !S_ISCHR(metadata.st_mode) || metadata.st_uid != 0 ||
      major(metadata.st_rdev) != 1 || minor(metadata.st_rdev) != 3) {
    fail("trusted null device identity changed");
  }
  return descriptor;
}

void duplicate_inherited_fd(int source, int target) {
  if (source == target) {
    if (::fcntl(target, F_SETFD, 0) != 0) {
      fail(errno_message("clear inherited descriptor close-on-exec"));
    }
    return;
  }
  if (::dup3(source, target, 0) != target) {
    fail(errno_message("dup3 inherited descriptor"));
  }
}

void close_untrusted_child_descriptors() {
  if (::syscall(SYS_close_range, kFirstClosedFd, kLastLowClosedFd,
                CLOSE_RANGE_UNSHARE) != 0 ||
      ::syscall(SYS_close_range, kFirstHighClosedFd,
                std::numeric_limits<unsigned int>::max(), 0) != 0) {
    fail(errno_message("close_range child descriptor boundary"));
  }
}

[[noreturn]] void child_exec(const ReceivedRequest& request, int snapshot_fd,
                             int handoff_socket, int loader_fd, int python_fd,
                             int null_device_fd) {
  try {
    duplicate_inherited_fd(null_device_fd, STDIN_FILENO);
    duplicate_inherited_fd(null_device_fd, STDOUT_FILENO);
    duplicate_inherited_fd(null_device_fd, STDERR_FILENO);
    duplicate_inherited_fd(snapshot_fd, kSnapshotFd);
    duplicate_inherited_fd(request.descriptors[1].get(), kArtifactDirectoryFd);
    duplicate_inherited_fd(request.descriptors[2].get(), kRuntimeDirectoryFd);
    duplicate_inherited_fd(handoff_socket, kHandoffSocketFd);
    duplicate_inherited_fd(loader_fd, kLoaderFd);
    duplicate_inherited_fd(python_fd, kPythonFd);
    close_untrusted_child_descriptors();
    if (::prctl(PR_SET_PDEATHSIG, SIGKILL) != 0 || ::getppid() <= 1) {
      fail("trusted supervisor parent-death binding failed");
    }
    if (::ptrace(PTRACE_TRACEME, 0, nullptr, nullptr) != 0 ||
        ::raise(SIGSTOP) != 0) {
      fail("trace exclusion could not start before credential drop");
    }
    if (::setgroups(0, nullptr) != 0 ||
        ::setresgid(request.peer.gid, request.peer.gid, request.peer.gid) != 0 ||
        ::setresuid(request.peer.uid, request.peer.uid, request.peer.uid) != 0 ||
        ::prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0 ||
        ::prctl(PR_SET_DUMPABLE, 0, 0, 0, 0) != 0 || ::chdir("/") != 0) {
      fail("tracee credential and no-new-privileges transition failed");
    }
    (void)::umask(0077);

    std::array<std::string, 18> argument_storage = launch_arguments();
    std::array<char*, 19> arguments{};
    for (std::size_t index = 0; index < argument_storage.size(); ++index) {
      arguments[index] = argument_storage[index].data();
    }
    std::array<std::string, 9> environment_storage = launch_environment();
    std::array<char*, 10> environment{};
    for (std::size_t index = 0; index < environment_storage.size(); ++index) {
      environment[index] = environment_storage[index].data();
    }
    ::syscall(SYS_execveat, kLoaderFd, "", arguments.data(), environment.data(),
              AT_EMPTY_PATH);
    fail(errno_message("execveat exact dynamic loader"));
  } catch (const std::exception& error) {
    const std::string message = std::string("supervisor child rejected: ") +
                                error.what() + "\n";
    [[maybe_unused]] const ssize_t write_result =
        ::write(STDERR_FILENO, message.data(), message.size());
    _exit(125);
  }
}

void send_handoff(int socket_descriptor, const HandoffWireV1& handoff,
                  const NamespaceHandles& namespaces) {
  UniqueFd receipt = create_sealed_memfd(
      "engine-v2-full-pipeline-cpu-supervisor-handoff-v1",
      reinterpret_cast<const uint8_t*>(&handoff), sizeof(handoff), 0400);
  const std::array<int, 3> descriptors = {
      receipt.get(), namespaces.user.get(), namespaces.mount.get()};
  std::array<char, CMSG_SPACE(sizeof(int) * descriptors.size())> control{};
  struct iovec vector {
    const_cast<HandoffWireV1*>(&handoff), sizeof(handoff)
  };
  struct msghdr message {};
  message.msg_iov = &vector;
  message.msg_iovlen = 1;
  message.msg_control = control.data();
  message.msg_controllen = control.size();
  struct cmsghdr* header = CMSG_FIRSTHDR(&message);
  header->cmsg_level = SOL_SOCKET;
  header->cmsg_type = SCM_RIGHTS;
  header->cmsg_len = CMSG_LEN(sizeof(int) * descriptors.size());
  std::memcpy(CMSG_DATA(header), descriptors.data(),
              sizeof(int) * descriptors.size());
  if (::sendmsg(socket_descriptor, &message, MSG_NOSIGNAL) !=
      static_cast<ssize_t>(sizeof(handoff))) {
    fail("kernel-attested supervisor handoff was not delivered exactly once");
  }
}

void require_exec_identity(pid_t child, int loader_fd) {
  struct stat expected {};
  struct stat observed {};
  const std::string path = "/proc/" + std::to_string(child) + "/exe";
  if (::fstat(loader_fd, &expected) != 0 || ::stat(path.c_str(), &observed) != 0 ||
      expected.st_dev != observed.st_dev || expected.st_ino != observed.st_ino) {
    fail("trace exec event did not enter the exact loader descriptor");
  }
}

struct TraceResult {
  int exit_code = 125;
  bool timed_out = false;
  bool containment_failure = false;
};

TraceResult trace_until_exit(pid_t root_child, int root_pidfd, int peer_pidfd,
                             int connection, uint32_t timeout_seconds,
                             int loader_fd, int handoff_socket,
                             const HandoffWireV1& handoff,
                             const NamespaceHandles& namespaces) {
  constexpr unsigned long kTraceOptions =
      PTRACE_O_TRACEEXEC | PTRACE_O_EXITKILL | PTRACE_O_TRACEFORK |
      PTRACE_O_TRACEVFORK | PTRACE_O_TRACECLONE;
  int status = 0;
  if (::waitpid(root_child, &status, __WALL) != root_child ||
      !WIFSTOPPED(status) || WSTOPSIG(status) != SIGSTOP) {
    fail("tracee did not stop before credential drop");
  }
  require_child_namespace_identity(root_child, namespaces);
  if (::ptrace(PTRACE_SETOPTIONS, root_child, nullptr, kTraceOptions) != 0) {
    fail(errno_message("PTRACE_SETOPTIONS"));
  }
  std::set<pid_t> tracees{root_child};
  bool initial_exec_observed = false;
  if (::ptrace(PTRACE_CONT, root_child, nullptr, nullptr) != 0) {
    fail(errno_message("PTRACE_CONT initial tracee"));
  }
  const auto deadline = std::chrono::steady_clock::now() +
                        std::chrono::seconds(timeout_seconds);
  TraceResult result;
  while (!tracees.empty()) {
    if (std::chrono::steady_clock::now() >= deadline) {
      result.timed_out = true;
      result.containment_failure = true;
      break;
    }
    const pid_t observed = ::waitpid(-1, &status, __WALL | WNOHANG);
    if (observed == 0) {
      std::array<pollfd, 3> poll_descriptors = {
          pollfd{root_pidfd, POLLIN | POLLHUP | POLLERR, 0},
          pollfd{peer_pidfd, POLLIN | POLLHUP | POLLERR, 0},
          pollfd{connection, POLLIN | POLLHUP | POLLERR, 0}};
      const int poll_result =
          ::poll(poll_descriptors.data(), poll_descriptors.size(), 10);
      if (poll_result < 0 && errno != EINTR) {
        fail(errno_message("poll traced process set"));
      }
      if (poll_descriptors[1].revents != 0 ||
          poll_descriptors[2].revents != 0) {
        result.containment_failure = true;
        break;
      }
      continue;
    }
    if (observed < 0) {
      if (errno == EINTR) {
        continue;
      }
      fail(errno_message("waitpid traced process set"));
    }
    if (WIFEXITED(status) || WIFSIGNALED(status)) {
      if (observed == root_child) {
        result.exit_code = WIFEXITED(status) ? WEXITSTATUS(status)
                                             : 128 + WTERMSIG(status);
      }
      tracees.erase(observed);
      continue;
    }
    if (!WIFSTOPPED(status)) {
      result.containment_failure = true;
      break;
    }
    const unsigned int event = static_cast<unsigned int>(status) >> 16U;
    const int stop_signal = WSTOPSIG(status);
    if (event == PTRACE_EVENT_EXEC) {
      if (observed != root_child || initial_exec_observed) {
        result.containment_failure = true;
        break;
      }
      require_exec_identity(root_child, loader_fd);
      require_child_namespace_identity(root_child, namespaces);
      send_handoff(handoff_socket, handoff, namespaces);
      initial_exec_observed = true;
    } else if (event == PTRACE_EVENT_FORK || event == PTRACE_EVENT_VFORK ||
               event == PTRACE_EVENT_CLONE) {
      unsigned long child_value = 0;
      if (::ptrace(PTRACE_GETEVENTMSG, observed, nullptr, &child_value) != 0 ||
          child_value == 0 ||
          child_value > static_cast<unsigned long>(
                            std::numeric_limits<pid_t>::max())) {
        result.containment_failure = true;
        break;
      }
      tracees.insert(static_cast<pid_t>(child_value));
    } else if (stop_signal != SIGSTOP && stop_signal != SIGTRAP) {
      if (::ptrace(PTRACE_CONT, observed, nullptr, stop_signal) != 0) {
        result.containment_failure = true;
        break;
      }
      continue;
    }
    if (::ptrace(PTRACE_SETOPTIONS, observed, nullptr, kTraceOptions) != 0 ||
        ::ptrace(PTRACE_CONT, observed, nullptr, nullptr) != 0) {
      result.containment_failure = true;
      break;
    }
  }
  if (!initial_exec_observed) {
    result.containment_failure = true;
  }
  if (result.timed_out || result.containment_failure) {
    for (const pid_t tracee : tracees) {
      (void)::ptrace(PTRACE_KILL, tracee, nullptr, nullptr);
      (void)::kill(tracee, SIGKILL);
    }
    while (::waitpid(-1, &status, __WALL | WNOHANG) > 0) {
    }
    result.exit_code = 125;
  }
  return result;
}

HandoffWireV1 build_handoff(const ReceivedRequest& request, pid_t child,
                            const NamespaceHandles& namespaces,
                            const FileBytes& source,
                            const FileBytes& supervisor_binary) {
  HandoffWireV1 handoff{};
  std::memcpy(handoff.magic, kHandoffMagic, sizeof(kHandoffMagic) - 1U);
  handoff.version_be = htonl(kProtocolVersion);
  handoff.size_be = htonl(sizeof(HandoffWireV1));
  handoff.nonce = request.wire.nonce;
  handoff.request_sha256 = request.request_sha256;
  handoff.activation_sha256 = request.wire.activation_sha256;
  handoff.preflight_sha256 = request.wire.preflight_sha256;
  handoff.profile_sha256 = request.wire.profile_sha256;
  handoff.runtime_manifest_sha256 = request.wire.runtime_manifest_sha256;
  handoff.source_snapshot_sha256 = source.digest;
  handoff.dynamic_loader_sha256 = digest_from_hex(kDynamicLoaderSha256);
  handoff.python_executable_sha256 = digest_from_hex(kPythonExecutableSha256);
  handoff.supervisor_binary_sha256 = supervisor_binary.digest;
  handoff.launch_vector_sha256 =
      canonical_vector_digest(launch_arguments());
  handoff.launch_environment_sha256 =
      canonical_vector_digest(launch_environment());
  handoff.peer_pid_be = htonl(static_cast<uint32_t>(request.peer.pid));
  handoff.peer_uid_be = htonl(static_cast<uint32_t>(request.peer.uid));
  handoff.peer_gid_be = htonl(static_cast<uint32_t>(request.peer.gid));
  handoff.child_pid_be = htonl(static_cast<uint32_t>(child));
  handoff.user_namespace_device_be =
      host_to_big_u64(static_cast<uint64_t>(namespaces.user_metadata.st_dev));
  handoff.user_namespace_inode_be =
      host_to_big_u64(static_cast<uint64_t>(namespaces.user_metadata.st_ino));
  handoff.mount_namespace_device_be =
      host_to_big_u64(static_cast<uint64_t>(namespaces.mount_metadata.st_dev));
  handoff.mount_namespace_inode_be =
      host_to_big_u64(static_cast<uint64_t>(namespaces.mount_metadata.st_ino));
  handoff.flags_be = htonl(kHandoffFlagExecObserved |
                           kHandoffFlagPeerCredentialBound |
                           kHandoffFlagNamespaceFdsBound);
  return handoff;
}

void send_terminal(int connection, const ReceivedRequest& request,
                   const TraceResult& result) {
  TerminalWireV1 terminal{};
  std::memcpy(terminal.magic, kTerminalMagic, sizeof(kTerminalMagic) - 1U);
  terminal.version_be = htonl(kProtocolVersion);
  terminal.size_be = htonl(sizeof(TerminalWireV1));
  terminal.nonce = request.wire.nonce;
  terminal.request_sha256 = request.request_sha256;
  terminal.exit_code_be = htonl(static_cast<uint32_t>(result.exit_code));
  uint32_t flags = 0;
  if (result.timed_out) {
    flags |= kTerminalFlagTimedOut;
  }
  if (result.containment_failure) {
    flags |= kTerminalFlagContainmentFailure;
  }
  terminal.flags_be = htonl(flags);
  if (::send(connection, &terminal, sizeof(terminal), MSG_NOSIGNAL) !=
      static_cast<ssize_t>(sizeof(terminal))) {
    fail("supervisor terminal receipt was not delivered exactly once");
  }
}

void handle_one_request(int connection, const NamespaceHandles& namespaces) {
  ReceivedRequest request = receive_request(connection);
  const uint32_t timeout_seconds = validate_request(request);
  UniqueFd peer_pidfd = open_socket_peer_pidfd(connection);
  FileBytes source = read_stable_file(request.descriptors[0].get(),
                                      kMaximumSourceBytes, "preflight source");
  if (digest_hex(source.digest) != kPreflightSha256 ||
      source.metadata.st_uid != request.peer.uid ||
      (source.metadata.st_mode & (S_IWGRP | S_IWOTH)) != 0 ||
      source.metadata.st_nlink != 1) {
    fail("preflight source identity or ownership changed");
  }
  UniqueFd snapshot = create_sealed_memfd(
      "engine-v2-full-pipeline-cpu-preflight-v1", source.raw.data(),
      source.raw.size(), 0444);
  UniqueFd loader = open_exact_root_executable(
      kDynamicLoaderPath, kDynamicLoaderSha256, "exact dynamic loader");
  UniqueFd python = open_exact_root_executable(
      kPythonExecutablePath, kPythonExecutableSha256,
      "exact Python executable");
  UniqueFd null_device = open_trusted_null_device();
  UniqueFd supervisor_descriptor(
      ::open("/proc/self/exe", O_RDONLY | O_CLOEXEC));
  if (!supervisor_descriptor.valid()) {
    fail("trusted supervisor executable descriptor is unavailable");
  }
  const FileBytes supervisor_binary = read_stable_file(
      supervisor_descriptor.get(), kMaximumExecutableBytes,
      "trusted supervisor executable");
  if (supervisor_binary.metadata.st_uid != 0 ||
      supervisor_binary.metadata.st_gid != 0 ||
      supervisor_binary.metadata.st_nlink != 1 ||
      (supervisor_binary.metadata.st_mode & (S_IWGRP | S_IWOTH)) != 0) {
    fail("trusted supervisor executable ownership changed");
  }
  std::array<int, 2> handoff_sockets{};
  if (::socketpair(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC, 0,
                   handoff_sockets.data()) != 0) {
    fail(errno_message("kernel handoff socketpair"));
  }
  UniqueFd parent_handoff(handoff_sockets[0]);
  UniqueFd child_handoff(handoff_sockets[1]);
  const pid_t child = ::fork();
  if (child < 0) {
    fail(errno_message("fork traced preflight"));
  }
  if (child == 0) {
    (void)parent_handoff.release();
    child_exec(request, snapshot.get(), child_handoff.get(), loader.get(),
               python.get(), null_device.get());
  }
  child_handoff = UniqueFd();
  UniqueFd child_pidfd(
      static_cast<int>(::syscall(SYS_pidfd_open, child, 0)));
  if (!child_pidfd.valid()) {
    (void)::kill(child, SIGKILL);
    fail("traced preflight pidfd is unavailable");
  }
  HandoffWireV1 handoff =
      build_handoff(request, child, namespaces, source, supervisor_binary);
  const TraceResult result = trace_until_exit(
      child, child_pidfd.get(), peer_pidfd.get(), connection, timeout_seconds,
      loader.get(),
      parent_handoff.get(), handoff, namespaces);
  send_terminal(connection, request, result);
}

UniqueFd bind_service_socket() {
  struct stat directory {};
  if (::stat("/run/betelgeuze-engine-v2", &directory) != 0 ||
      !S_ISDIR(directory.st_mode) || directory.st_uid != 0 ||
      directory.st_gid != 0 || (directory.st_mode & (S_IWGRP | S_IWOTH)) != 0) {
    fail("root-owned supervisor runtime directory is unavailable");
  }
  UniqueFd socket_descriptor(
      ::socket(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC, 0));
  if (!socket_descriptor.valid()) {
    fail(errno_message("create supervisor socket"));
  }
  struct sockaddr_un address {};
  address.sun_family = AF_UNIX;
  if (std::strlen(kSocketPath) >= sizeof(address.sun_path)) {
    fail("supervisor socket path exceeds sockaddr_un");
  }
  std::strncpy(address.sun_path, kSocketPath, sizeof(address.sun_path) - 1U);
  if (::bind(socket_descriptor.get(),
             reinterpret_cast<const struct sockaddr*>(&address),
             sizeof(address)) != 0 ||
      ::chown(kSocketPath, 0, kExpectedClientGid) != 0 ||
      ::chmod(kSocketPath, 0660) != 0 ||
      ::listen(socket_descriptor.get(), 1) != 0) {
    fail(errno_message("bind absent-only supervisor socket"));
  }
  return socket_descriptor;
}

__attribute__((noinline)) bool client_identity_is_configured() {
  volatile const uid_t observed_uid = kExpectedClientUid;
  volatile const gid_t observed_gid = kExpectedClientGid;
  return observed_uid != std::numeric_limits<uid_t>::max() &&
         observed_gid != std::numeric_limits<gid_t>::max() &&
         observed_uid != 0;
}

__attribute__((used, noinline)) int run_service() {
  if (::geteuid() != 0 || ::getegid() != 0 ||
      !client_identity_is_configured()) {
    fail("trusted supervisor provisioning identity is incomplete");
  }
  if (::prctl(PR_SET_DUMPABLE, 0, 0, 0, 0) != 0 ||
      ::prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0) {
    fail("trusted supervisor hardening failed");
  }
  NamespaceHandles namespaces = open_initial_namespace_handles();
  UniqueFd service = bind_service_socket();
  UniqueFd connection(
      ::accept4(service.get(), nullptr, nullptr, SOCK_CLOEXEC));
  if (!connection.valid()) {
    fail(errno_message("accept supervisor request"));
  }
  handle_one_request(connection.get(), namespaces);
  return 0;
}

void describe_contract() {
  std::cout
      << "{\"authority_false\":true,\"client_gid\":"
      << static_cast<uintmax_t>(kExpectedClientGid)
      << ",\"client_identity_configured\":"
      << (client_identity_is_configured() ? "true" : "false")
      << ",\"client_uid\":" << static_cast<uintmax_t>(kExpectedClientUid)
      << ",\"handoff_bytes\":"
      << sizeof(HandoffWireV1)
      << ",\"installation_authorized\":false,"
         "\"operational\":false,\"protocol_version\":"
      << kProtocolVersion << ",\"qualification_consumption_authorized\":false,"
      << "\"request_bytes\":" << sizeof(RequestWireV1)
      << ",\"required_request_fds\":" << kRequiredRequestFds
      << ",\"runtime_launch_authorized\":false,\"schema_id\":"
         "\"betelgeuze.engine_v2_full_pipeline_cpu_supervisor/1.0.0\","
         "\"supervisor_id\":\""
      << kSupervisorId << "\",\"preflight_sha256\":\"" << kPreflightSha256
      << "\",\"terminal_bytes\":" << sizeof(TerminalWireV1)
      << "}\n";
}

void self_test_primitives() {
  constexpr std::string_view kSha256TestInput = "abc";
  constexpr char kSha256TestExpected[] =
      "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";
  const auto observed_sha256 = sha256(
      reinterpret_cast<const uint8_t*>(kSha256TestInput.data()),
      kSha256TestInput.size());
  const bool sha256_valid = digest_hex(observed_sha256) == kSha256TestExpected;
  const bool launch_vector_valid =
      digest_hex(canonical_vector_digest(launch_arguments())) ==
      kLaunchVectorSha256;
  const bool launch_environment_valid =
      digest_hex(canonical_vector_digest(launch_environment())) ==
      kLaunchEnvironmentSha256;
  const bool digest_round_trip_valid =
      digest_hex(digest_from_hex(kPreflightSha256)) == kPreflightSha256;
  if (!sha256_valid || !launch_vector_valid || !launch_environment_valid ||
      !digest_round_trip_valid) {
    fail("supervisor primitive self-test failed");
  }
  std::cout
      << "{\"authority_false\":true,\"digest_round_trip\":true,"
         "\"launch_environment_sha256\":\""
      << kLaunchEnvironmentSha256 << "\",\"launch_vector_sha256\":\""
      << kLaunchVectorSha256
      << "\",\"service_started\":false,\"sha256_abc\":true}\n";
}

}  // namespace

int main(int argc, char** argv) {
  if (argc == 2 && std::string_view(argv[1]) == "--describe-contract") {
    describe_contract();
    return 0;
  }
  if (argc == 2 && std::string_view(argv[1]) == "--self-test-primitives") {
    try {
      self_test_primitives();
      return 0;
    } catch (const std::exception& error) {
      std::cerr << "Engine V2 full-pipeline CPU supervisor self-test failed: "
                << error.what() << '\n';
      return 125;
    }
  }
  if (!kInstallationAuthorized || !kRuntimeLaunchAuthorized ||
      !kQualificationConsumptionAuthorized) {
    std::cerr
        << "Engine V2 full-pipeline CPU supervisor is source-complete but "
           "non-operational: installation, runtime launch, and qualification "
           "consumption remain unauthorized; activation_sha256="
        << kActivationSha256 << '\n';
    return 125;
  }
  try {
    return run_service();
  } catch (const std::exception& error) {
    std::cerr << "Engine V2 full-pipeline CPU supervisor failed closed: "
              << error.what() << '\n';
    return 125;
  }
}
