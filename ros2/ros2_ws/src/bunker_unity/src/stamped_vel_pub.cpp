#include <chrono>
#include <functional>
#include <memory>
#include <string>

#include "rclcpp/rclcpp.hpp"
#include "geometry_msgs/msg/twist.hpp"
#include "geometry_msgs/msg/twist_stamped.hpp"

using namespace std::chrono_literals;

class StampedVelocityPub : public rclcpp::Node
{
public:
  StampedVelocityPub()
  : Node("stamped_vel_pub"), count_(0)
  {
    publisher_ = this->create_publisher<geometry_msgs::msg::TwistStamped>("cmd_vel_stamped", 10);
    subscription_ = this->create_subscription<geometry_msgs::msg::Twist>(
      "cmd_vel_out_unstamped", 10, std::bind(&StampedVelocityPub::cmd_vel_callback, this, std::placeholders::_1));
    timer_ = this->create_wall_timer(
    20ms, std::bind(&StampedVelocityPub::timer_callback, this));
  }

private:
  void timer_callback()
  {
    auto message = geometry_msgs::msg::TwistStamped();
    message.header.stamp = this->get_clock()->now();
    message.twist.linear.x = input_cmd_vel_.linear.x;
    message.twist.linear.y = input_cmd_vel_.linear.y;
    message.twist.angular.z = input_cmd_vel_.angular.z;

    publisher_->publish(message);
  }

  void cmd_vel_callback(const geometry_msgs::msg::Twist::SharedPtr msg)
  {
    input_cmd_vel_.linear.x = msg->linear.x;
    input_cmd_vel_.linear.y = msg->linear.y;
    input_cmd_vel_.angular.z = msg->angular.z;

  }
  rclcpp::TimerBase::SharedPtr timer_;
  rclcpp::Publisher<geometry_msgs::msg::TwistStamped>::SharedPtr publisher_;
  rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr subscription_;
  geometry_msgs::msg::Twist input_cmd_vel_;
  size_t count_;
};

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<StampedVelocityPub>());
  rclcpp::shutdown();
  return 0;
}

