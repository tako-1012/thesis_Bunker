using UnityEngine;
using Unity.Robotics.Core;
using RosMessageTypes.Nav;
using RosMessageTypes.Geometry;
using Unity.Robotics.ROSTCPConnector;
using System;
using Unity.Robotics.ROSTCPConnector.ROSGeometry;
using RosMessageTypes.Tf2;

public class PerfectOdometryPublisher : MonoBehaviour
{
    // Topic to publish odometry data
    public string odometryTopic = "/perfect_odometry";
    public string topicName = "tf";

    // Publishing rate (in Hz)
    public float publishRate = 10.0f;
    float time;
    // ROS TCP Connector instance
    private ROSConnection rosConnection;

    public Vector3<FLU> local_pose;
    public QuaternionMsg local_rot;


    private void Start()
    {
        // Create a ROS connection
        rosConnection = ROSConnection.GetOrCreateInstance();
        rosConnection.RegisterPublisher<OdometryMsg>(odometryTopic);
        rosConnection.RegisterPublisher<TFMessageMsg>(topicName);
    }

    void FixedUpdate()
        {
            time += Time.deltaTime;
            if (time<0.05f) return;
            time = 0.0f;
            local_pose=transform.localPosition.To<FLU>();
            local_rot=transform.localRotation.To<FLU>();
            PublishOdometry();
            PublishTransform();
        }

    private void PublishTransform()
    {
        TFMessageMsg tfMessage = new TFMessageMsg(new TransformStampedMsg[] { CreateTransform() });
        rosConnection.Publish(topicName, tfMessage);
    }
    TransformStampedMsg CreateTransform()
    {
        // Create the odometry message
        TransformStampedMsg msg = new TransformStampedMsg{
            header = new RosMessageTypes.Std.HeaderMsg
            {
                stamp = new TimeStamp(Clock.Now),
                frame_id = "perfect_odom"
            },
            transform = new TransformMsg(local_pose,local_rot),
            child_frame_id = "base_link"
        };

        return msg;
    }
    private void PublishOdometry()
    {
        
        // Create the odometry message
        PoseMsg pose = new PoseMsg{
            position = local_pose,
            orientation = local_rot
            
        };

        PoseWithCovarianceMsg posewithcov = new PoseWithCovarianceMsg{
            pose = pose,
            covariance = new double[36]
        };

        
        // Create the odometry message
        OdometryMsg odometryMessage = new OdometryMsg
        {
            header = new RosMessageTypes.Std.HeaderMsg
            {
                stamp = new TimeStamp(Clock.Now),
                frame_id = "perfect_odom"
            },
            pose = posewithcov,
            child_frame_id = "base_link"
        };


        // Publish the odometry message to the ROS topic
        rosConnection.Publish(odometryTopic, odometryMessage);
    }
  
}